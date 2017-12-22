## Copyright 2016-2017 Gorm Andresen (Aarhus University), Jonas Hoersch (FIAS), Tom Brown (FIAS)

## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 3 of the
## License, or (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Renewable Energy Atlas Lite (Atlite)

Light-weight version of Aarhus RE Atlas for converting weather data to power systems data
"""

from __future__ import absolute_import

import xarray as xr
import pandas as pd
import numpy as np
import os, shutil
import logging
import tempfile
import shutil
import subprocess
from glob import glob
from six import itervalues
from six.moves import map
from multiprocessing import Pool

logger = logging.getLogger(__name__)

def cutout_do_task(task, write_to_file=True):
    task = task.copy()
    prepare_func = task.pop('prepare_func')
    if write_to_file:
        datasetfns = task.pop('datasetfns')

    try:
        if 'fn' in task:
            fn = task.pop('fn')
            engine = task.pop('engine')
            task['ds'] = xr.open_dataset(fn, engine=engine)
        data = prepare_func(**task)
        if data is None:
            data = []

        if write_to_file:
            for yearmonth, ds in data:
                ## TODO : rewrite using plain netcdf4 to add variables
                ## to the same file one by one
                fn = datasetfns[yearmonth]
                ds.to_netcdf(fn)
                logger.debug("Write variable(s) %s to %s generated by %s",
                             ", ".join(ds.data_vars),
                             os.path.basename(fn),
                             prepare_func.__name__)
        else:
            return [(ym,ds.load()) for ym, ds in data]
    except Exception as e:
        logger.exception("Exception occured in the task with prepare_func `%s`: %s",
                         prepare_func.__name__, e.args[0])
        raise e
    finally:
        if 'ds' in task:
            task['ds'].close()

def cutout_prepare(cutout, overwrite=False, nprocesses=None, gebco_height=False):
    if cutout.prepared and not overwrite:
        raise ArgumentError("The cutout is already prepared. If you want to recalculate it, "
                            "anyway, then you must supply an `overwrite=True` argument.")

    logger.info("Starting preparation of cutout '%s'", cutout.name)

    cutout_dir = cutout.cutout_dir
    yearmonths = cutout.coords['year-month'].to_index()
    xs = cutout.coords['x']
    ys = cutout.coords['y']

    if gebco_height:
        logger.info("Interpolating gebco to the dataset grid")
        cutout.meta['height'] = _prepare_gebco_height(xs, ys)

    # Delete cutout_dir
    if os.path.isdir(cutout_dir):
        logger.debug("Deleting cutout_dir '%s'", cutout_dir)
        shutil.rmtree(cutout_dir)

    os.mkdir(cutout_dir)
    cutout.meta.unstack('year-month').to_netcdf(cutout.datasetfn())

    # Compute data and fill files
    tasks = []
    for series in itervalues(cutout.weather_data_config):
        series = series.copy()
        series['meta_attrs'] = cutout.meta.attrs
        tasks_func = series.pop('tasks_func')
        tasks += tasks_func(xs=xs, ys=ys, yearmonths=yearmonths, **series)
    for i, t in enumerate(tasks):
        def datasetfn_with_id(ym):
            base, ext = os.path.splitext(cutout.datasetfn(ym))
            return base + "-{}".format(i) + ext
        t['datasetfns'] = {ym: datasetfn_with_id(ym) for ym in yearmonths.tolist()}

    logger.info("%d tasks have been collected. Starting running them on %s.",
                len(tasks),
                ("%d processes" % nprocesses)
                if nprocesses is not None
                else "all processors")

    pool = Pool(processes=nprocesses)
    try:
        pool.map(cutout_do_task, tasks)
    except Exception as e:
        pool.terminate()
        logger.info("Preparation of cutout '%s' has been interrupted by an exception. "
                    "Purging the incomplete cutout_dir.",
                    cutout.name)
        shutil.rmtree(cutout_dir)
        raise e
    pool.close()

    logger.info("Merging variables into monthly compound files")

    for fn in map(cutout.datasetfn, yearmonths.tolist()):
        base, ext = os.path.splitext(fn)
        fns = glob(base + "-*" + ext)

        with xr.open_mfdataset(fns) as ds:
            if gebco_height:
                ds['height'] = cutout.meta['height']

            ds.to_netcdf(fn)

        for fn in fns: os.unlink(fn)
        logger.debug("Completed file %s", os.path.basename(fn))

    logger.info("Cutout '%s' has been successfully prepared", cutout.name)
    cutout.prepared = True

def cutout_produce_specific_dataseries(cutout, yearmonth, series_name):
    xs = cutout.coords['x']
    ys = cutout.coords['y']
    series = cutout.weather_data_config[series_name].copy()
    series['meta_attrs'] = cutout.meta.attrs
    tasks_func = series.pop('tasks_func')
    tasks = tasks_func(xs=xs, ys=ys, yearmonths=[yearmonth], **series)

    assert len(tasks) == 1
    data = cutout_do_task(tasks[0], write_to_file=False)
    assert len(data) == 1 and data[0][0] == yearmonth
    return data[0][1]

def cutout_get_meta(cutout, xs, ys, years, months=None, **dataset_params):
    if months is None:
        months = slice(1, 12)
    meta_kwds = cutout.meta_data_config.copy()
    meta_kwds.update(dataset_params)

    prepare_func = meta_kwds.pop('prepare_func')
    ds = prepare_func(xs=xs, ys=ys, year=years.stop, month=months.stop, **meta_kwds)
    ds.attrs.update(dataset_params)

    start, second, end = map(pd.Timestamp, ds.coords['time'].values[[0, 1, -1]])
    month_start = pd.Timestamp("{}-{}".format(years.stop, months.stop))

    offset_start = (start - month_start)
    offset_end = (end - (month_start + pd.offsets.MonthBegin()))
    step = (second - start).components.hours

    ds.coords["time"] = pd.date_range(
        start=pd.Timestamp("{}-{}".format(years.start, months.start)) + offset_start,
        end=(month_start + pd.offsets.MonthBegin() + offset_end),
        freq='h' if step == 1 else ('%dh' % step))

    ds.coords["year"] = range(years.start, years.stop+1)
    ds.coords["month"] = range(months.start, months.stop+1)
    ds = ds.stack(**{'year-month': ('year', 'month')})

    return ds

def cutout_get_meta_view(cutout, xs=None, ys=None, years=slice(None), months=slice(None), **dataset_params):
    meta = cutout.meta

    if xs is not None:
        meta.attrs.setdefault('view', {})['x'] = xs
    if ys is not None:
        meta.attrs.setdefault('view', {})['y'] = ys

    meta = (meta
            .unstack('year-month')
            .sel(year=years, month=months, **meta.attrs.get('view', {}))
            .stack(**{'year-month': ('year', 'month')}))

    meta = meta.sel(time=slice(*("{:04}-{:02}".format(*ym)
                                 for ym in meta['year-month'][[0,-1]].to_index())))

    return meta


def _prepare_gebco_height(xs, ys):
    # gebco bathymetry heights for underwater
    from .config import gebco_path

    tmpdir = tempfile.mkdtemp()
    cornersc = np.array(((xs[0], ys[0]), (xs[-1], ys[-1])))
    minc = np.minimum(*cornersc)
    maxc = np.maximum(*cornersc)
    span = (maxc - minc)/(np.asarray((len(xs), len(ys)))-1)
    minx, miny = minc - span/2.
    maxx, maxy = maxc + span/2.

    tmpfn = os.path.join(tmpdir, 'resampled.nc')
    try:
        ret = subprocess.call(['gdalwarp', '-of', 'NETCDF',
                               '-ts', str(len(xs)), str(len(ys)),
                               '-te', str(minx), str(miny), str(maxx), str(maxy),
                               '-r', 'average',
                               gebco_path, tmpfn])
        assert ret == 0, "gdalwarp was not able to resample gebco"
    except OSError:
        logger.warning("gdalwarp was not found for resampling gebco. "
                       "Next-neighbour interpolation will be used instead!")
        tmpfn = gebco_path

    with xr.open_dataset(tmpfn) as ds_gebco:
        height = (ds_gebco.rename({'lon': 'x', 'lat': 'y', 'Band1': 'height'})
                          .reindex(x=xs, y=ys, method='nearest')
                          .load()['height'])
    shutil.rmtree(tmpdir)
    return height

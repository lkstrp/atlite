import os
from functools import wraps
from pathlib import Path
import shutil
import pytest
from atlite import Cutout

TIME = "2013-01-01"
BOUNDS = (-4, 56, 1.5, 62)
SARAH_DIR = os.getenv("SARAH_DIR", "/home/vres/climate-data/sarah_v2")
GEBCO_PATH = os.getenv("GEBCO_PATH", "/home/vres/climate-data/GEBCO_2014_2D.nc")


os.environ["ATLITE_CACHE_PATH"] = "/Users/lukas/.cache/atlite_tests_cache"


@pytest.fixture(scope="session", autouse=True)
def cutouts_path(tmp_path_factory):
    env_path = os.getenv("ATLITE_CACHE_PATH")
    if env_path:
        path = Path(env_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    else:
        raise Exception("ATLITE_CACHE_PATH not set")
        return tmp_path_factory


@pytest.fixture(scope="session")
def cutout_era5(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5.nc"
    cutout = Cutout(path=tmp_path, module="era5", bounds=BOUNDS, time=TIME)
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_era5_3h_sampling(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5_3h_sampling.nc"
    time = [
        f"{TIME} 00:00",
        f"{TIME} 03:00",
        f"{TIME} 06:00",
        f"{TIME} 09:00",
        f"{TIME} 12:00",
        f"{TIME} 15:00",
        f"{TIME} 18:00",
        f"{TIME} 21:00",
    ]
    cutout = Cutout(path=tmp_path, module="era5", bounds=BOUNDS, time=time)
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_era5_2days_crossing_months(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5_2days_crossing_months.nc"
    time = slice("2013-02-28", "2013-03-01")
    cutout = Cutout(path=tmp_path, module="era5", bounds=BOUNDS, time=time)
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_era5_coarse(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5_coarse.nc"
    cutout = Cutout(
        path=tmp_path, module="era5", bounds=BOUNDS, time=TIME, dx=0.5, dy=0.7
    )
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_era5_weird_resolution(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5_weird_resolution.nc"
    cutout = Cutout(
        path=tmp_path,
        module="era5",
        bounds=BOUNDS,
        time=TIME,
        dx=0.132,
        dy=0.32,
    )
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_era5_reduced(cutouts_path):
    tmp_path = cutouts_path / "cutout_era5_reduced.nc"
    cutout = Cutout(path=tmp_path, module="era5", bounds=BOUNDS, time=TIME)
    return cutout


@pytest.fixture(scope="session")
def cutout_sarah(cutouts_path):
    tmp_path = cutouts_path / "cut_out_sarah.nc"
    cutout = Cutout(
        path=tmp_path,
        module=["sarah", "era5"],
        bounds=BOUNDS,
        time=TIME,
        sarah_dir=SARAH_DIR,
    )
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_sarah_fine(cutouts_path):
    tmp_path = cutouts_path / "cutout_sarah_fine.nc"
    cutout = Cutout(
        path=tmp_path,
        module="sarah",
        bounds=BOUNDS,
        time=TIME,
        dx=0.05,
        dy=0.05,
        sarah_dir=SARAH_DIR,
    )
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_sarah_weird_resolution(cutouts_path):
    tmp_path = cutouts_path / "cutout_sarah_weird_resolution.nc"
    cutout = Cutout(
        path=tmp_path,
        module="sarah",
        bounds=BOUNDS,
        time=TIME,
        dx=0.132,
        dy=0.32,
        sarah_dir=SARAH_DIR,
    )
    cutout.prepare()
    return cutout


@pytest.fixture(scope="session")
def cutout_gebco(cutouts_path):
    tmp_path = cutouts_path / "cutout_gebco.nc"
    cutout = Cutout(
        path=tmp_path,
        module="gebco",
        bounds=BOUNDS,
        time=TIME,
        gebco_path=GEBCO_PATH,
    )
    cutout.prepare()
    return cutout

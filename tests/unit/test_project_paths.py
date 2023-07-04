import os.path

import pytest

from tasks.dao.ProjectPaths import ProjectPaths, RepoPaths
from tasks.models.ConstellationSpecV01 import Cluster, Constellation


@pytest.fixture(scope="session")
def constellation():
    return Constellation(
        name='saturn',
        bary=Cluster(name='saturn'),
        satellites=[
            Cluster(name='titan'),
            Cluster(name='rhea')
        ])


@pytest.fixture(scope="session")
def tmp_abs_root_directory(tmp_path_factory):
    return tmp_path_factory.mktemp("tmp_root")


def test_dir_tree_repo():
    rpaths = RepoPaths()
    assert rpaths.apps_dir() == os.path.join(
        os.getcwd(),
        'apps'
    )


def test_config_dir_from_absolute_root_env(monkeypatch, constellation, tmp_abs_root_directory):
    monkeypatch.setenv('GOCY_ROOT', tmp_abs_root_directory)

    cfg_dir = ProjectPaths()
    assert cfg_dir.project_root() == str(tmp_abs_root_directory)


def test_config_dir_from_absolute_root(constellation):
    tmp_root = os.path.join("/tmp", "gocy")
    ppath = ProjectPaths(constellation_name='saturn', cluster_name='saturn', root=tmp_root)
    assert ppath.patches_dir() == os.path.join(
            tmp_root,
            'saturn',
            'saturn',
            'patch'
        )


def test_config_dir_constellation_root(constellation):
    ppath = ProjectPaths(constellation_name=constellation.name, root='tmp_root')

    assert ppath.constellation_dir() == os.path.join(
            os.path.expanduser('~'),
            'tmp_root',
            'saturn'
        )


def test_config_dir_cluster_root(constellation):
    root = '.gocy_tmp_root'
    ppath = ProjectPaths(constellation_name=constellation.name, cluster_name='titan', root=root)

    assert ppath.patches_dir() == os.path.join(
            os.path.expanduser('~'),
            root,
            constellation.name,
            'titan',
            'patch'
        )


def test_dir_tree_config_sub_dir(constellation):
    ppath = ProjectPaths(constellation_name=constellation.name, cluster_name='rhea')
    assert ppath.patches_dir('bgp') == os.path.join(
            os.path.expanduser('~'),
            '.gocy',
            'saturn',
            'rhea',
            'patch',
            'bgp'
        )
from unittest.mock import Mock

from dronedelivery.problem.objects.grid import Location
from dronedelivery.problem.objects.warehouse import WareHouse
from tests.fixtures import full_problem


def test_warehouses_in_environment(full_problem):
    environment = full_problem.get_environment()
    for warehouse in full_problem.warehouses:
        assert warehouse in environment


def test_orders_in_environment(full_problem):
    environment = full_problem.get_environment()
    for order in full_problem.orders:
        assert order in environment


def test_get_all_locations(full_problem):
    environment = full_problem.get_environment()
    assert (
        len(list(environment.get_all_locations()))
        == full_problem.grid.n_x * full_problem.grid.n_y
    )


def test_get_nearest_warehouse(full_problem):
    environment = full_problem.get_environment()
    place1 = Mock()
    place1.location = Location(x=10, y=30)
    nearest_warehouse = environment.get_nearest_warehouse(place1)
    assert isinstance(nearest_warehouse, WareHouse)


def test_get_distance(full_problem):
    environment = full_problem.get_environment()

    place1 = Location(x=10, y=40)
    place2 = Location(x=15, y=50)
    distance = environment.get_distance(place1, place2)
    assert distance == 12

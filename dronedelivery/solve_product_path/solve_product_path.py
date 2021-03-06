import itertools
from dataclasses import dataclass

from dronedelivery.utils.mip_utils.variables import IntegerVariable
from dronedelivery.utils.mip_utils.linear_expression import LinearExpression
from dronedelivery.utils.mip_utils.constraints import (
    EqualityConstraint,
    LE_InequalityConstraint,
)
from dronedelivery.utils.mip_utils.model import Model
from dronedelivery.problem.objects import Product


@dataclass
class Trip:
    origin: str
    destination: str
    product_type: Product
    product_quantity: int


class SolveProductTrips:
    def __init__(self, customers, hubs, products, max_flight_capacity, environment):
        self.environment = environment
        self.max_flight_capacity = max_flight_capacity

        decision_variables = self.get_variables(customers, hubs, products)
        objective = self.get_objective(customers, hubs)
        constraints = self.get_constraints(customers, hubs, products)

        self.model = Model(
            decision_variables=decision_variables,
            objective=objective,
            constraints=constraints,
        )

    def solve(self, Mip_Solver, max_seconds=120):
        mip_solver = Mip_Solver(model=self.model)
        solution = mip_solver.solve(max_seconds=max_seconds)
        trips = self._get_trips(solution)
        return trips

    def _get_trips(self, solution):
        trips_hub_to_customer = []
        trips_hub_to_hub = []
        for variable, value in solution.items():
            if value != 0 and isinstance(variable, ProductsMoveCustomerHub):
                trips_hub_to_customer.append(
                    Trip(
                        origin=variable.data["hub"],
                        destination=variable.data["customer"],
                        product_type=variable.data["product"],
                        product_quantity=value,
                    )
                )
            if value != 0 and isinstance(variable, ProductsMoveHubHub):
                trips_hub_to_hub.append(
                    Trip(
                        origin=variable.data["hub1"],
                        destination=variable.data["hub2"],
                        product_type=variable.data["product"],
                        product_quantity=value,
                    )
                )

        return {
            "hub_to_customer": trips_hub_to_customer,
            "hub_to_hub": trips_hub_to_hub,
        }

    def get_variables(self, customers, hubs, products):
        self.n_flights_variables = self._get_n_flights_variables(customers, hubs)
        self.n_product_move_variables = self._get_n_products_move_variables(
            customers, hubs, products
        )
        self.n_flights_hub_to_hub_variables = self._get_n_flights_hub_to_hub(hubs)
        self.n_products_move_hub_to_hub_variables = (
            self._get_n_products_move_hub_to_hub(hubs, products)
        )
        return (
            list(self.n_flights_variables.values())
            + list(self.n_product_move_variables.values())
            + list(self.n_flights_hub_to_hub_variables.values())
            + list(self.n_products_move_hub_to_hub_variables.values())
        )

    def get_objective(self, customers, hubs):
        le = LinearExpression()
        for customer, hub in itertools.product(customers, hubs):
            le.add_variable(
                variable=self.n_flights_variables[customer, hub],
                coefficient=self.environment.get_distance(hub.location, customer.location),
            )

        for hub1, hub2 in itertools.product(hubs, hubs):
            if hub1 != hub2:
                le.add_variable(
                    variable=self.n_flights_hub_to_hub_variables[hub1, hub2],
                    coefficient=self.environment.get_distance(hub1.location, hub2.location),
                )
        return le

    def get_constraints(self, customers, hubs, products):
        demand_constraints = self._get_demand_constraints(customers, products, hubs)
        supply_constraints = self._get_supply_constraints(customers, products, hubs)
        trips_constraints = self._get_trips_constraints(customers, products, hubs)
        trips_hub_hub_constraints = self._get_trips_hub_to_hub_constraints(
            products, hubs
        )
        return (
            demand_constraints
            + supply_constraints
            + trips_constraints
            + trips_hub_hub_constraints
        )

    def _get_n_flights_variables(self, customers, hubs):
        return {
            (customer, hub): FlightsCustomerHub(
                name={f"number of flights from {hub} to {customer}"},
                lower_bound=0,
                data={"customer": customer, "hub": hub},
            )
            for customer, hub in itertools.product(customers, hubs)
        }

    def _get_n_products_move_variables(self, customers, hubs, products):
        return {
            (customer, hub, product): ProductsMoveCustomerHub(
                name={
                    f"number of products of product type {product} from {hub} to {customer}"
                },
                lower_bound=0,
                upper_bound=customer.demand[product]
                if product in customer.demand
                else 0,
                data={"customer": customer, "hub": hub, "product": product},
            )
            for customer, hub, product in itertools.product(customers, hubs, products)
        }

    def _get_n_flights_hub_to_hub(self, hubs):
        return {
            (hub1, hub2): FlightsHubHub(
                name={f"number of flights from {hub1} to {hub2}"},
                lower_bound=0,
                data={"hub1": hub1, "hub2": hub2},
            )
            for hub1, hub2 in itertools.product(hubs, hubs)
            if hub1 != hub2
        }

    def _get_n_products_move_hub_to_hub(self, hubs, products):
        return {
            (hub1, hub2, product): ProductsMoveHubHub(
                name={
                    f"number of products of product type {product} from {hub1} to {hub2}"
                },
                lower_bound=0,
                data={"hub1": hub1, "hub2": hub2, "product": product},
            )
            for hub1, hub2, product in itertools.product(hubs, hubs, products)
            if hub1 != hub2
        }

    def _get_demand_constraints(self, customers, products, hubs):
        constraints = []
        for customer, product in itertools.product(customers, products):
            if product in customer.demand:
                lhs = LinearExpression()
                for hub in hubs:
                    lhs.add_variable(
                        self.n_product_move_variables[(customer, hub, product)]
                    )
                constraints.append(
                    EqualityConstraint(lhs=lhs, rhs=customer.demand[product])
                )
        return constraints

    def _get_supply_constraints(self, customers, products, hubs):
        constraints = []
        for hub, product in itertools.product(hubs, products):
            le_1 = LinearExpression()
            for customer in customers:
                le_1.add_variable(
                    self.n_product_move_variables[(customer, hub, product)]
                )

            le_2 = LinearExpression()
            for hub_ in hubs:
                if hub_ != hub:
                    le_2.add_variable(
                        self.n_products_move_hub_to_hub_variables[(hub_, hub, product)],
                        1,
                    )
                    le_2.add_variable(
                        self.n_products_move_hub_to_hub_variables[(hub, hub_, product)],
                        -1,
                    )

            constraints.append(
                LE_InequalityConstraint(
                    lhs=le_1 - le_2, rhs=hub.get_available_items(product)
                )
            )
        return constraints

    def _get_trips_constraints(self, customers, products, hubs):
        constraints = []
        for customer, hub in itertools.product(customers, hubs):
            le_1 = LinearExpression()
            for product in products:
                le_1.add_variable(
                    self.n_product_move_variables[(customer, hub, product)]
                )

            le_2 = LinearExpression()
            le_2.add_variable(
                self.n_flights_variables[(customer, hub)], self.max_flight_capacity
            )

            constraints.append(LE_InequalityConstraint(lhs=le_1 - le_2, rhs=0))
        return constraints

    def _get_trips_hub_to_hub_constraints(self, products, hubs):
        constraints = []
        for hub1, hub2 in itertools.product(hubs, hubs):
            if hub1 != hub2:
                le_1 = LinearExpression()
                for product in products:
                    le_1.add_variable(
                        self.n_products_move_hub_to_hub_variables[(hub1, hub2, product)]
                    )

                le_2 = LinearExpression()
                le_2.add_variable(
                    self.n_flights_hub_to_hub_variables[(hub1, hub2)],
                    self.max_flight_capacity,
                )

                constraints.append(LE_InequalityConstraint(lhs=le_1 - le_2, rhs=0))
        return constraints


class FlightsCustomerHub(IntegerVariable):
    pass


class ProductsMoveCustomerHub(IntegerVariable):
    pass


class FlightsHubHub(IntegerVariable):
    pass


class ProductsMoveHubHub(IntegerVariable):
    pass

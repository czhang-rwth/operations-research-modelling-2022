#!/usr/bin/env python3
from gurobipy import *
import networkx as nx
import math


# This function can stay unchanged
def prepare_output(cities, G, x, y):
    """Takes the input graph and adds the flows of commodities and planes to the edge data for plotting. Also sets the node location based on their timestamp, allowing us to plot the time-expanded network

    Args:
        cities (dict): Maps city names to their location in the 2D plane, e.g., {"cityname": (10,5)}
        G (nx.DiGraph): Graph of the time-expanded network, with node names like ("cityname", 2) where the second tuple element is the timestep. Additionally, each arc has have a list of commodities that can use it as an attribute.
        x (dict): Dictionary of gurobi variables for the commodity flow in the form {(commodity, arc): variable}. Arc is an element of G.edges and commodity is an element of cities
        y (dict): Dictionary of gurobi variables for the plane flow {arc: variable}

    Returns:
        nx.DiGraph: Graph of the time-expanded network with additional edge and node information
    """

    ## Add flow values
    commodity_flows = {
        arc: {c: x[c, arc].x for c in G.get_edge_data(*arc)["commodities"]}
        for arc in G.edges
    }
    plane_flows = {arc: y[arc].x for arc in G.edges}

    nx.set_edge_attributes(G, commodity_flows, "commodities")
    nx.set_edge_attributes(G, plane_flows, "planes")

    # Set location of nodes by city (sorted alphabetically) and timestamp
    city_to_index = {c: i for i, c in enumerate(sorted(cities))}
    location = {node: (node[1], city_to_index[node[0]]) for node in G.nodes}

    nx.set_node_attributes(G, location, "pos")
    return G


# Lots of work to do in this function!
def solve(full_instance_path):
    """Solving function, takes an instance file, constructs the time-expanded network, builds and solves a gurobi model and returns the solution.

    Args:
        full_instance_path (string): Path to the instance file to read in

    Returns:
        model: Gurobi model after solving
        cities (dict): Maps city names to their location in the 2D plane, e.g., {"cityname": (10,5)}
        G (nx.DiGraph): Graph of the time-expanded network with additional edge and node information
        x (dict): Dictionary of gurobi variables for the commodity flow in the form {(commodity, arc): variable}. Arc is an element of G.edges and commodity is an element of cities
        y (dict): Dictionary of gurobi variables for the plane flow {arc: variable}
    """

    # Read in the instance data
    # ???, ???, ... = read_instance(full_instance_path)  # --- TODO ---
    data = read_instance(full_instance_path)
    cities = {}  # --- TODO
    hubs = []
    terminals = []
    key_cities = return_key(dict_=data, value_='CITIES')
    key_demand = return_key(dict_=data, value_='DEMAND')

    for i in range(key_cities+1, key_demand):
        cities[data[i][0]] = (int(data[i][1]), int(data[i][2]))
        if data[i][3][0] == 'H':
            hubs.append(data[i][0])
        if data[i][3][0] == 'T':
            terminals.append(data[i][0])
    
    for i in data:
        for j in range(len(data[i])):
            if data[i][j] == 'NUMBER':
                num_planes = int(data[i][-1][:-1])
                break
            if data[i][j] == 'HORIZON':
                try:
                    time_horizon = int(data[i][-1][:-1])
                except:
                    time_horizon = float(data[i][-1][:-1])
                break
            if data[i][j] == 'RESOLUTION':
                try:
                    time_resolution = int(data[i][-1][:-1])
                except:
                    time_resolution = float(data[i][-1][:-1])
                break
            if data[i][j] == 'LIMIT':
                try:
                    weight_limit = int(data[i][-1][:-1])
                except:
                    weight_limit = float(data[i][-1][:-1])
                break
            if data[i][j] == 'AIRPORT':
                try:
                    airport_cost = int(data[i][-1][:-1])
                except:
                    airport_cost = float(data[i][-1][:-1])
                break
            if data[i][j] == 'PLANE' and data[i][j+1] == 'FIXED' and j == 0:
                try:
                    plane_cost = int(data[i][-1][:-1])
                except:
                    plane_cost = float(data[i][-1][:-1])
                break
            if data[i][j] == 'FUEL':
                try:
                    fuel_cost = int(data[i][-1][:-1])
                except:
                    fuel_cost = float(data[i][-1][:-1])
                break
            if data[i][j] == 'SPEED':
                try:
                    plane_speed = int(data[i][-1][:-1])
                except:
                    plane_speed = float(data[i][-1][:-1])
                break

    T = [i for i in range(int(time_horizon/time_resolution)+1)]

    demand = {}
    for i in range(key_demand+1, len(data)+1):
        try:
            demand[(data[i][0],data[i][1])] = int(data[i][-1][:-1])
        except:
            demand[(data[i][0],data[i][1])] = float(data[i][-1][:-1])
    
    for f1 in cities:
        for f2 in cities:
            if not (f1,f2) in demand:
                demand[(f1,f2)] = 0

    # Construct graph --- NOTE: You do not have to use networkx for this task, but it is strongly recommended and necessary for the plotting functions given
    G = nx.DiGraph()  # Replace with:
    # G = build_graph(???)  # --- TODO ---

    # Add node to the graph 
    for t in T:
        for city in cities:
            G.add_node((city,t))
    
    # Add A_hold to the graph 
    for t in T[:-1]:
        for city in cities:
            G.add_edge((city,t), (city,t+1))

    # Add A_link to the graph
    for city_start in cities:
        for city_end in cities:
            if city_end == city_start:
                continue
            fly_time_abs = distance(cities[city_start],cities[city_end])/plane_speed
            fly_time_ref = math.ceil(fly_time_abs/time_resolution)
            for t in range(T[-1] - fly_time_ref + 1):
                G.add_edge((city_start, t), (city_end, t+fly_time_ref))

    # create Commodities
    facilities = [i for i in cities]

    commodities = {}
    for arc in G.edges:
        commodities[arc] = []
        for f in facilities:
            for t in T:
                if nx.has_path(G, (f,t), arc[1]) == True:
                    commodities[arc].append(f)
    
    nx.set_edge_attributes(G, commodities, 'commodities')
        
    # === Gurobi model ===
    model = Model("SND")

    # --- Variables ---

    # Commodity arc variables
    # x (dict): Dictionary of gurobi variables for the commodity flow in the form {(commodity, arc): variable}. 
    # Arc is an element of G.edges and commodity is an element of cities
    x = {}  # --- TODO ---
    for arc in G.edges:
        for f in facilities:
            x[(f, arc)] = model.addVar(name="x_%s_(%s,%s)_(%s,%s)" % (f,arc[0][0], arc[0][1],arc[1][0],arc[1][1]), vtype = GRB.CONTINUOUS, lb=0)

    # Airplane arc variables
    # y (dict): Dictionary of gurobi variables for the plane flow {arc: variable}
    y = {}  # --- TODO ---
    for arc in G.edges:
        y[arc] = model.addVar(name="y_(%s,%s)_(%s,%s)" % (arc[0][0], arc[0][1],arc[1][0],arc[1][1]), vtype = GRB.INTEGER, lb=0, ub = num_planes)

    # Potentially additional variables ? --- TODO ---
    model.modelSense = GRB.MINIMIZE
    model.setObjective(quicksum(y[arc]*(airport_cost + fuel_cost*distance(cities[arc[0][0]],cities[arc[1][0]])) for arc in G.edges if arc[0][0] != arc[1][0]) 
                     + quicksum(y[arc]*plane_cost for arc in G.edges if arc[0][1] == 0))
                        
    # --- Constraints
    # --- TODO ---

    for f1 in facilities:
        for v in G.nodes:
            if v == (f1, 0):
                model.addConstr(quicksum(x[(f1, arc)] for arc in G.out_edges(v)) - 
                                quicksum(x[(f1, arc)] for arc in G.in_edges(v)) ==
                                quicksum(demand[(f1,fi)] for fi in facilities))
            
            elif v[1] == T[-1]:
                model.addConstr(quicksum(x[(f1, arc)] for arc in G.out_edges(v)) -
                                quicksum(x[(f1, arc)] for arc in G.in_edges(v)) == 
                                -demand[(f1, v[0])])
            
            else:
                model.addConstr(quicksum(x[(f1, arc)] for arc in G.out_edges(v)) ==
                                quicksum(x[(f1, arc)] for arc in G.in_edges(v)))

    for node in G.nodes:
        if node[-1] != 0 and node[-1] != T[-1]:
            model.addConstr(quicksum(y[arc_out] for arc_out in G.out_edges(node)) == 
                            quicksum(y[arc_in] for arc_in in G.in_edges(node)))

    model.addConstr(quicksum(y[arc] for arc in G.edges if arc[0][1] == 0) ==
                    quicksum(y[arc] for arc in G.edges if arc[1][1] == T[-1]))

    model.addConstr(quicksum(y[arc] for arc in G.edges if arc[0][1] == 0) <= num_planes)

    for arc in G.edges:
        if arc[0][0] != arc[1][0]:
            model.addConstr(quicksum(x[(f, arc)] for f in facilities) <= weight_limit*y[arc])

    for f in facilities:
        for arc in G.edges:
            if arc[0][0] != arc[1][0] and arc[0][0] in terminals and f != arc[0][0]:
                model.addConstr(x[f, arc] == 0)

    #for node in G.nodes:
    #    if node[0] in terminals:
    #        for f in facilities:
    #            if f != node[0]:
    #                model.addConstr(quicksum(x[(f, arc)] for arc in G.out_edges(node) if arc[1][0] != node[0]) == 0)

    # Solve the model
    model.update()
    model.optimize()
    # If your model is infeasible (but you expect it to not be), comment out the lines below to compute and write out a infeasible subsystem (Might take very long)
    #model.computeIIS()
    #model.write("model.ilp")

    if model.status == GRB.OPTIMAL:
        print('\n objective: %g\n' % model.ObjVal)

        for f in facilities:
            for arc in G.edges:
                if x[(f,arc)].x != 0:
                    #print("x_%s_(%s,%s)_(%s,%s) = %s" % (f,arc[0][0], arc[0][1],arc[1][0],arc[1][1],x[(f,arc)].x))
                    print(x[(f, arc)])
        
        for arc in G.edges:
            if y[arc].x != 0:
                #print("y_(%s,%s)_(%s,%s) = %s" % (arc[0][0], arc[0][1],arc[1][0],arc[1][1],y[arc].x))
                print(y[arc])

    else:
        print("No solution!")

    return model, cities, G, x, y

def distance(a:tuple, b:tuple) -> float:
    d = ( (a[0] - b[0])**2 + (a[1] - b[1])**2 )**0.5
    return d


# --- TODO ---
# This function is missing not only its content but also a proper signature (which arguments do you want to pass?) as well as documentation!
# As a sidenote, in most code editors you can add function comment strings like below automatically with a key combination. For VSC, the extension autoDocstring is necessary.
def build_graph(some_argument, another_argument):
    """Constructs the time-expanded network

    Args:
        some_argument (datatype): What is this?
        another_argument (datatype): Good documentation is important!

    Returns:
        nx.DiGraph: Graph of the time-expanded network
    """

    # New directed graph
    G = nx.DiGraph()

    # Adding nodes --- TODO ---

    # Adding arcs (with attributes) --- TODO ---

    return G


# --- TODO ---
# Same to-dos as for build_graph()
def read_instance(full_instance_path): #to create the dict of cities 
    """Reads in instance data

    Args:
        full_instance_path (string): Path to the instance file to read in

    Returns:
        (some datatype(s)): what do you want to return?
    """

    some_stuff = {}

    data = open(full_instance_path)

    i = 1
    for line in data:
        line = line.split(' ')
        some_stuff[i] = line
        i += 1

    return some_stuff

def return_key(dict_: dict, value_: str) -> int:
    for i in dict_:
        if value_ in dict_[i][0]:
            return i


if __name__ == "__main__":
    # --- Optional TODO ---
    # Using the argparse library you can write a nice CLI so that you can test your code easier (without having to change the instance string manually etc.)
    instance = './data1.dat'
    solve(instance)

from gurobipy import *


def solve(a, p, b): #a: size   p:profit   b:capacity 
    nitems = len(p)
    items = range(nitems)

    # Do not change the following line!
    vertices = [(c, i) for i in range(nitems+1) for c in range(b+2)]
    # TODO: Generate arcs ----------------------------------------

    # KEY OF THIS PROBLEM => CAPACITY+1!!!!!!
    arcs_horizon = [((c,i),(c+1,i),0) for i in range(nitems+1) for c in range(b+1)]
    arcs_vertical = [((c,i),(c,i+1),0) for i in range(nitems) for c in range(b+2)]
    a.insert(0,0)
    p.insert(0,0)
    arcs_profile = [((c,i),(c+a[i+1]+1,i+1),p[i+1]) for i in range(nitems) for c in range(b+1-(a[i+1]+1)+1)]
    arcs = arcs_horizon + arcs_vertical + arcs_profile  # Use whatever format suits your needs

    star_in, star_out = {},{}

    for arc in arcs:
        if not arc[0] in star_out:
            star_out[arc[0]] = []
        star_out[arc[0]].append(arc[0:2])

        if not arc[1] in star_in:
            star_in[arc[1]] = []
        star_in[arc[1]].append(arc[0:2])
    # ------------------------------------------------------------------------

    # Model
    model = Model("Flowbased knapsack")
    model.modelSense = GRB.MAXIMIZE

    # Decision variable x_a indicates whether arc a is selected (value 1) or
    # not (value 0)
    # TODO: Adjust string formatting (behind the "%" sign) so that the --------
    # variables in the gurobi model will have the correct name! Also use
    # reasonable dict keys for x[...] =
    x = {}
    for arc in arcs:
        x[arc[0],arc[1]] = model.addVar(name="x_(%s,%s),(%s,%s)" % (arc[0][0],arc[0][1],arc[1][0],arc[1][1]), vtype=GRB.BINARY, obj=arc[2])
    # -------------------------------------------------------------------------

    # Update the model to make variables known.
    # From now on, no variables should be added.
    model.update()

    # TODO: Add your constraints ----------------------------------------------

    # the forward star of the source is 1
    model.addConstr(quicksum(x[arc[0],arc[1]] for arc in arcs if arc[0]==(0,0)) 
                    - quicksum(x[arc[0],arc[1]] for arc in arcs if arc[1] == (0,0)) == 1)

    # the backward star of the senke is -1
    model.addConstr(quicksum(x[arc[0],arc[1]] for arc in arcs if arc[0]==(b+1,nitems)) 
                    - quicksum(x[arc[0],arc[1]] for arc in arcs if arc[1] == (b+1,nitems)) == -1)

    model.addConstrs(quicksum(x[arc[0], arc[1]] for arc in star_out[vertex])
                     == quicksum(x[arc[0], arc[1]] for arc in star_in[vertex]) for vertex in vertices if not (vertex == (0,0) or vertex==(b+1,nitems)))
    # -------------------------------------------------------------------------

    model.update()
    # For debugging: print your model
    # model.write('model.lp')
    model.optimize()

    # TODO: Adjust your dict keys for x[...] to print out the selected --------
    # edges from your solution and then uncomment those lines.
    # This is not not necessary for grading but helps you confirm that your
    # model works

    # Printing solution and objective value
    def printSolution():
        if model.status == GRB.OPTIMAL:
            print('\n objective: %g\n' % model.ObjVal)
            print("Selected following arcs:")
            for arc in arcs:
                if x[arc[0],arc[1]].x == 1:
                    print(arc)
        else:
            print("No solution!")
    # -------------------------------------------------------------------------

    printSolution()
    # Please do not delete the following line
    return model

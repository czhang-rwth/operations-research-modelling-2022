from gurobipy import *
import pandas as pd
import sqlite3

def solve(database_path, json_path, objective):

    # READ DATA
    image_vec = pd.read_json(json_path)

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    sql = "select name from sqlite_master where type='table'"
    cursor.execute(sql)
    database = {}
    for table in cursor.fetchall():
        df = pd.read_sql_query("select * from "+ table[0], conn)
        database[table[0]] = {}
        for column in df.columns:
            database[table[0]][column] = list(df[column])
    conn.close()

    for i in database:
        for j in database[i]:
            print(i, j, database[i][j])

    # category_style{category_id=1} = [3,4,,8,9,10 style_id]
    category_style = {}  
    for i in database['categories']['id']:
        category_style[i] = []
        for j in range(len(database['style_categories']['category_id'])):
            if database['style_categories']['category_id'][j] == i:
                category_style[i].append(database['style_categories']['style_id'][j])

    # CREATE MODEL
    model = Model('product diversity')

    # Variables 
    x = {}
    z = {}
    for i in database['styles']['id']:
        for s in database['shops']['id']:
            x[(s,i)] = model.addVar(name="x_%s_%s" % (s,i), vtype = 'N', lb=database['styles']['min_shipment'][i-1])
            z[(s,i)] = model.addVar(name="z_%s_%s" % (s,i), vtype = 'B')

    y = {}
    for i in database['styles']['id']:
        for j in database['styles']['id']:
            if i >= j: # make sure i < j 
                continue
            for s in database['shops']['id']:
                y[(s,(i,j))] = model.addVar(name="y_%s_(%s_%s)" % (s,i,j), vtype = 'B')

    # auxiliary variable to linearize the mean calculation
    u = {}
    for i in database['styles']['id']:
        for s in database['shops']['id']:
            u[(s,i)] = model.addVar(name="u_%s_%s" % (s,i), vtype = 'C', lb=0)#, ub=1)

    w = {}
    for i in database['styles']['id']:
        for j in database['styles']['id']:
            if i >= j: # make sure i < j 
                continue
            for s in database['shops']['id']:
                w[(s,(i,j))] = model.addVar(name="w_%s_(%s_%s)" % (s,i,j), vtype = 'C', lb=0)#, ub=1)

    # reciprocal of the number of different styles distributed to store s
    r = {}
    for s in database['shops']['id']:
        r[s] = model.addVar(name='r_%s' % s, vtype = 'C', lb=0, ub=1)#lb=1/database['styles']['id'][-1], ub=1/2)

    # Objective function 
    model.modelSense = GRB.MAXIMIZE

    if objective == 'MaxSumSum':
        model.setObjective(quicksum(y[(s,(i,j))]*euclidean(image_vec[i],image_vec[j]) 
                                    for s in database['shops']['id']
                                    for i in database['styles']['id']
                                    for j in database['styles']['id']
                                    if i < j))

    if objective == 'MaxMean':
        model.setObjective(quicksum(w[(s,(i,j))]*euclidean(image_vec[i],image_vec[j]) 
                                    for s in database['shops']['id']
                                    for i in database['styles']['id']
                                    for j in database['styles']['id']
                                    if i < j))

    #Constraints 

    # there should not be to much or to little of each color at each store
    for color_id in database['colors']['id']:
        min_percentage = database['colors']['min_percentage'][color_id-1]
        max_percentage = database['colors']['max_percentage'][color_id-1]

        for s in database['shops']['id']:
            model.addConstr(quicksum(x[(s,i)] for i in database['styles']['id'] if database['styles']['color_id'][i-1] == color_id) >=
                            min_percentage*quicksum(x[(s,i)] for i in database['styles']['id']))

            model.addConstr(quicksum(x[(s,i)] for i in database['styles']['id'] if database['styles']['color_id'][i-1] == color_id) <=
                            max_percentage*quicksum(x[(s,i)] for i in database['styles']['id']))

    # each store specifies how many units of each category they need at least and at most
    for j in range(len(database['shop_categories']['shop_id'])):
        shop_id = database['shop_categories']['shop_id'][j]
        category_id = database['shop_categories']['category_id'][j]
        min_delivery = database['shop_categories']['min_delivery'][j]
        max_delivery = database['shop_categories']['max_delivery'][j]

        model.addConstr(quicksum(x[(shop_id,i)] for i in category_style[category_id]) >= min_delivery)
        model.addConstr(quicksum(x[(shop_id,i)] for i in category_style[category_id]) <= max_delivery)

    # there is only a limited supply of each style available
    for i in database['styles']['id']:
        max_shipment = database['styles']['supply'][i-1]
        model.addConstr(quicksum(x[(s,i)] for s in database['shops']['id']) <= max_shipment)            
    
    # Linking x and z[s,i], z[s,i] and y[s,i,j] 
    for s in database['shops']['id']:
        for i in database['styles']['id']:
            model.addConstr(x[(s,i)] >= z[(s,i)])
            for j in database['styles']['id']:
                if i >= j: # make sure i < j 
                    continue
                model.addConstr(z[(s,i)] >= y[(s,(i,j))])
                model.addConstr(z[(s,j)] >= y[(s,(i,j))])
    
    # linearize the mean calculation 
    for s in database['shops']['id']:
        model.addConstr(quicksum(z[(s,i)] for i in database['styles']['id']) >= 2)
        #model.addConstr(r[s]*quicksum(z[(s,i)] for i in database['styles']['id']) == 1)
        if objective == 'MaxSumSum':
            continue 

        # the following is about MaxMean 
        model.addConstr(quicksum(u[(s,i)] for i in database['styles']['id']) == 1) 
        for i in database['styles']['id']:
            model.addConstr(u[(s,i)] >= r[s] + z[(s,i)] - 1)
            model.addConstr(u[(s,i)] <= r[s])
            model.addConstr(u[(s,i)] <= z[(s,i)])
            for j in database['styles']['id']:
                if i >= j:
                    continue
                model.addConstr(w[(s,(i,j))] >= r[s] + z[(s,i)] + z[(s,j)] - 2)
                model.addConstr(w[(s,(i,j))] <= r[s])
                model.addConstr(w[(s,(i,j))] <= z[(s,i)])
                model.addConstr(w[(s,(i,j))] <= z[(s,j)])

    model.update()
    model.optimize()

    if model.status == GRB.OPTIMAL:
        print('\n objective: %g\n' % model.ObjVal)

        for s in database['shops']['id']:
            for i in database['styles']['id']:
                print(x[(s,i)], u[(s,i)])

        for s in database['shops']['id']:
            print(r[s])

        for i in database['styles']['id']:
            for j in database['styles']['id']:
                if i >= j: # make sure i < j 
                    continue
                for s in database['shops']['id']:
                    print(w[(s,(i,j))])

    else:
        print('No Solution!')

    return model

def euclidean(vec1, vec2):
    distance = 0

    for i in range(len(vec1.index)):
        distance += (vec1[i] - vec2[i]) ** 2
    
    distance = distance ** 0.5

    return distance 

if __name__ == "__main__":
    solve('./pd.db', './image2vec.json', 'MaxMean')
from gurobipy import * 
import pandas as pd 
import networkx as nx 

def solve(full_path_instance):

    ########## read data ########## 
    data = open(full_path_instance)

    is_course, is_room, is_curricula, is_unavailability = False, False, False, False  

    index_course, index_room, index_curricula, index_unavailability = 0, 0, 0, 0

    for line in data:

        line = line.split()

        if line == []:
            continue

        if line[0] == 'Courses:':
            course = pd.DataFrame(index=list(range(int(line[1]))), columns=['CourseID', 'Teacher', 'Num Lectures', 'MinWorkingDays', 'Num Students'])

        if line[0] == 'Rooms:':
            room = pd.DataFrame(index=list(range(int(line[1]))), columns=['RoomID', 'Capacity'])
        
        if line[0] == 'Days:':
            days = int(line[1])

        if line[0] == 'Periods_per_day:':
            periods_per_day = int(line[1])

        if line[0] == 'Curricula:':
            num_curricula = int(line[1])
            curricula = {}

        if line[0] == 'Constraints:':
            unavailability = pd.DataFrame(index=list(range(int(line[1]))), columns=['CourseID', 'Day', 'Day_Period'])

        if line[0] == 'COURSES:':
            is_course = True 
            continue

        if is_course:
            course.loc[index_course, 'CourseID'] = line[0]
            course.loc[index_course, 'Teacher'] = line[1]
            course.loc[index_course, 'Num Lectures'] = int(line[2])
            course.loc[index_course, 'MinWorkingDays'] = int(line[3])
            course.loc[index_course, 'Num Students'] = int(line[4])
            
            if index_course == len(course.index) - 1:
                is_course = False 
            else:
                index_course += 1 
        
        if line[0] == 'ROOMS:':
            is_room = True
            continue

        if is_room:
            room.loc[index_room, 'RoomID'] = line[0]
            room.loc[index_room, 'Capacity'] = int(line[1])

            if index_room == len(room.index) - 1:
                is_room = False
            else:
                index_room += 1 

        if line[0] == 'CURRICULA:':
            is_curricula = True
            continue

        if is_curricula:
            curricula[line[0]] = []

            for i in range(2, len(line)):
                curricula[line[0]].append(line[i])

            if index_curricula == num_curricula - 1:
                is_curricula = False 
            else:
                index_curricula += 1 

        if line[0] == 'UNAVAILABILITY_CONSTRAINTS:':
            is_unavailability = True 
            continue

        if is_unavailability:
            if len(line) < 3:
                is_unavailability = False
            else:
                unavailability.loc[index_unavailability, 'CourseID'] = line[0]
                unavailability.loc[index_unavailability, 'Day'] = int(line[1])
                unavailability.loc[index_unavailability, 'Day_Period'] = int(line[2])

                if index_unavailability == len(unavailability.index) - 1:
                    is_unavailability = False 
                else:
                    index_unavailability += 1 

    data.close()

    teacher = {}
    for index in course.index:
        if course.loc[index, 'Teacher'] not in teacher.keys():
            teacher[course.loc[index, 'Teacher']] = []
        teacher[course.loc[index, 'Teacher']].append(course.loc[index, 'CourseID'])

    ########## Penalty ########## 
    c_assistant, c_students, c_days, c_teacher = 1, 0.1, 0.1, 10

    ########## Data we have ##########
    # Dataframe: course, room, unavailability
    # Dictionary: curricula, teacher
    # Constant: days, periods_per_day
    # Penalties: c_assistant, c_students, c_days, c_teacher 

    ########## create model ########## 
    model = Model('time tables')
    
    ########## create variable ########## 
    x = {}
    for k in course['CourseID']:
        for i in range(days):
            for j in range(periods_per_day):
                x[k,(i,j)] = model.addVar(name="x_%s_(%s,%s)" % (k,i,j), vtype = 'B')

    x_day = {}
    for k in course['CourseID']:
        for i in range(days):
            x_day[k,i] = model.addVar(name="x_day_%s_%s" % (k,i), vtype = 'B')

    z_day = {}
    for k in course['CourseID']:
        z_day[k] = model.addVar(name="z_day_%s" % k, vtype = 'I', lb = 0, ub = days)

    z_assistant = {}
    for t in teacher.keys():
        for i in range(days):
            for j in range(periods_per_day):
                z_assistant[t,(i,j)] = model.addVar(name='z_assistant_%s_(%s,%s)' % (t,i,j), vtype = 'I', lb = 0)

    z_students = {}
    c_k1_k2 = []
    for index1 in course.index:
        k1 = course.loc[index1, 'CourseID']

        for index2 in course.index:
            if index1 >= index2:
                continue

            k2 = course.loc[index2, 'CourseID']

            for c in curricula:
                if k1 in curricula[c] and k2 in curricula[c]:
                    c_k1_k2.append((c,k1,k2))

                    for i in range(days):
                        for j in range(periods_per_day):
                            z_students[(c,k1,k2), (i,j)] = model.addVar(name='z_students_(%s,%s,%s)_(%s,%s)' % (c, k1, k2, i, j), vtype = 'B')

    z_teacher = {}
    k_i_j = []
    for index in unavailability.index:
        k = unavailability.loc[index, 'CourseID']
        i = unavailability.loc[index, 'Day']
        j = unavailability.loc[index, 'Day_Period']
        k_i_j.append((k,i,j))
        z_teacher[(k,i,j)] = model.addVar(name='z_teacher_(%s,%s,%s)' % (k,i,j), vtype = 'B')

    print('\n##### All Data read, Lets Go ! #####\n')

    ########## Objective function ########## 
    model.modelSense = GRB.MINIMIZE

    model.setObjective(c_days * quicksum(z_day[k] for k in course['CourseID'])+ 
                       c_assistant * quicksum(z_assistant[t,(i,j)] for t in teacher.keys() for i in range(days) for j in range(periods_per_day))+
                       c_students * quicksum(z_students[(c,k1,k2),(i,j)] for (c,k1,k2) in c_k1_k2 for i in range(days) for j in range(periods_per_day))+
                       c_teacher * quicksum(z_teacher[(k,i,j)] for (k,i,j) in k_i_j))

    ########## constraints ########## 

    # For every course, a given number of lectures have to be scheduled
    for index in course.index:
        k = course.loc[index, 'CourseID']
        model.addConstr(quicksum(x[k,(i,j)] for i in range(days) for j in range(periods_per_day)) == course.loc[index, 'Num Lectures'])

    # The lectures of a given course have to take place on at least d_k different days
    for index in course.index:
        k = course.loc[index, 'CourseID']
        model.addConstr(quicksum(x_day[k,i] for i in range(days)) + z_day[k] >= course.loc[index, 'MinWorkingDays'])

    for i in range(days):
        for k in course['CourseID']:
            model.addConstr(quicksum(x[k,(i,j)] for j in range(periods_per_day)) >= x_day[k,i])

    # Courses taught by the same teacher can not take place in the same time slot
    for t in teacher.keys():
        model.addConstrs(quicksum(x[k,(i,j)] for k in teacher[t]) <= 1 + z_assistant[t,(i,j)] for i in range(days) for j in range(periods_per_day))

    # Courses that are part of the same curriculum can not take place in the same time slot
    for index1 in course.index:
        k1 = course.loc[index1, 'CourseID']

        for index2 in course.index:
            if index1 >= index2:
                continue

            k2 = course.loc[index2, 'CourseID']

            for c in curricula:
                if k1 in curricula[c] and k2 in curricula[c]:
                    model.addConstrs(x[k1,(i,j)] + x[k2,(i,j)] <= 1 + z_students[(c,k1,k2),(i,j)] for i in range(days) for j in range(periods_per_day))
                    break

    # For a variety of reasons, some unavailability constraints are given, such that courses k can not take place in some time-slots (i,j)
    for index in unavailability.index:
        k = unavailability.loc[index, 'CourseID']
        i = unavailability.loc[index, 'Day']
        j = unavailability.loc[index, 'Day_Period']
        
        model.addConstr(x[k,(i,j)] <= z_teacher[(k,i,j)]) # question why <= instead of == ? 

    model.update()

    ########## row generation ##########
    G = nx.DiGraph()
    G.add_nodes_from(course['CourseID'])
    G.add_nodes_from(room['RoomID'])
    G.add_nodes_from(['s', 't'])
    
    for k in course['CourseID']:
        G.add_edge('s', k, capacity=0)
    
    for r in room['RoomID']:
        G.add_edge(r, 't', capacity=1)

    for index_k in course.index:
        k = course.loc[index_k, 'CourseID']
        num_students = course.loc[index_k, 'Num Students']

        for index_r in room.index:
            r = room.loc[index_r, 'RoomID']
            capacity = room.loc[index_r, 'Capacity']

            if num_students <= capacity:
                G.add_edge(k, r, capacity=1)

    def callback(model, where):
        if where == GRB.Callback.MIPSOL:
            rel = model.cbGetSolution(x)
            for i in range(days):
                for j in range(periods_per_day):
                    k_1 = []
                    for k in course['CourseID']:
                        G.edges[('s',k)]['capacity'] = max(0, rel[k,(i,j)])
                        if round(rel[k,(i,j)]) == 1:
                            k_1.append(k)
                    flow = nx.maximum_flow_value(G, 's', 't')
                    if len(k_1) > round(flow):
                        model.cbLazy(quicksum(x[k,(i,j)] for k in k_1) <= flow)

    model.params.LazyConstraints = 1
    model.optimize(callback)  

    if model.status == GRB.OPTIMAL:
        print('\n objective: %g\n' % model.ObjVal)
    else:
        print('no solution !')

    return model  

if __name__ == "__main__":
    solve(full_path_instance = r'E:\OR_Coding\POM\university timetabling\comp02.ctt')
from py2neo import Node, Relationship
from typing import Any, Dict
import pandas
from scipy.stats import ttest_ind
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from scipy.stats import f_oneway
import ast
import os
import numpy as np
from scipy import stats
from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import json
import urllib.parse
from lib_save import connect_to_db
from lib_build import BuildDatabase, BuildDataStore
from data_to_db import FeedIntoNeo4j
from data_receiver import data_receiver, dict_to_txt

app = FastAPI()

# Allow cross domain requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return 'success'


GRAPH_CRYO = connect_to_db('cryo')
GRAPH_CPA = connect_to_db('cpa')


@app.get("/freeQueryCryo/{query}")
def freeQueryCryo(query):
    query = urllib.parse.unquote(query)
    return GRAPH_CRYO.run(query).data()


@app.get("/freeQueryCpa/{query}")
def freeQueryCpa(query):
    query = urllib.parse.unquote(query)
    return GRAPH_CPA.run(query).data()


@app.get("/cleanDatabase/{db_id}")
def cleanDatabase(db_id):
    if db_id == 'cryo':
        BuildDatabase(GRAPH_CRYO, 'cryo').delete_all()
    elif db_id == 'cpa':
        BuildDatabase(GRAPH_CPA, 'cpa').delete_all()
    return f'SUCCESS: DATABASE {db_id} CLEANED'


@app.get("/initDatabase/{db_id}")
def initDatabase(db_id):
    if db_id == 'cryo':
        cleanDatabase('cryo')
        BuildDatabase(GRAPH_CRYO, 'cryo').add_constraint()
    elif db_id == 'cpa':
        cleanDatabase('cpa')
        BuildDatabase(GRAPH_CPA, 'cpa').add_constraint()
    return f'SUCCESS: DATABASE {db_id} INIT'


@app.get("/connectDatabase/{db_id}")
def connectDatabase(db_id):
    if db_id == 'cryo':
        return BuildDatabase(GRAPH_CRYO, 'cryo').query_all()
    elif db_id == 'cpa':
        return BuildDatabase(GRAPH_CPA, 'cpa').query_all()


@app.get("/findIsolatedNodes/{db_id}")
def findIsolatedNodes(db_id):
    if db_id == 'cryo':
        return BuildDatabase(GRAPH_CRYO, 'cryo').find_isolated_nodes()
    elif db_id == 'cpa':
        return BuildDatabase(GRAPH_CPA, 'cpa').find_isolated_nodes()


@app.get("/buildDataStore/{store_name}")
def buildDataStore(store_name):
    return BuildDataStore(store_name).create_data_store_folder()


@app.get("/deleteDataStore/{store_name}")
def deleteDataStore(store_name):
    return BuildDataStore(store_name).delete_folder()


@app.get("/deleteOneType/")
def deleteOneType(store_name, data_type):
    return BuildDataStore(store_name).delete_one_type(data_type)


@app.get("/checkIntegrity/")
def checkIntegrity(store_name, data_type):
    todo = data_type.split(',')
    response = {}
    for file in todo:
        response[file] = BuildDataStore(store_name).create_one_type(file)
    return response


@app.get("/cleanLog/{log_id}")
def cleanLog(log_id):
    try:
        file_path = f'log/{log_id}.txt'
        with open(file_path, 'w') as file:
            file.truncate(0)
        return (f"Cleared file: {file_path}")
    except Exception as e:
        return 'error'


@app.get("/seeLog/{log_id}")
def seeLog(log_id):
    pass


@app.post("/fileUpload/")
async def fileUpload(files: list[UploadFile], data_type, data_store):
    res = []
    if data_type == 'CPA':
        for file in files:
            file_name = "/".join(file.filename.split("/")[-3:])
            upload_result = data_receiver(f'{data_store}/{data_type}/{file_name}', await file.read(), data_type)
            res.append({'file_name': file_name, 'result': upload_result,
                       'neo4j': 'waiting' if upload_result == 'success' else 'undo'})
        return str(res)
    else:
        for file in files:
            upload_result = data_receiver(f'{data_store}/{data_type}/{file.filename}', await file.read(), data_type)
            res.append({'file_name': file.filename, 'result': upload_result,
                       'neo4j': 'waiting' if upload_result == 'success' else 'undo'})
        return str(res)


@app.post("/fileCreate/")
async def fileCreate(files: list[UploadFile], data_type, data_store):
    res = []
    if data_type == 'CPA':
        for file in files:
            file_name = "/".join(file.filename.split("/")[-3:])
            upload_result = data_receiver(f'{data_store}/{data_type}/{file_name}', dict_to_txt(await file.read(), data_type, file_name), data_type)
            res.append({'file_name': file_name, 'result': upload_result,
                       'neo4j': 'waiting' if upload_result == 'success' else 'undo'})
        return str(res)
    else:
        for file in files:
            upload_result = data_receiver(f'{data_store}/{data_type}/{file.filename}', dict_to_txt(await file.read(), data_type, file.filename), data_type)
            res.append({'file_name': file.filename, 'result': upload_result,
                       'neo4j': 'waiting' if upload_result == 'success' else 'undo'})
        return str(res)


@app.get("/feedInNeo/")
def feedInNeo(data_type, file_name, data_store):
    try:
        if data_type == 'CPA':
            return FeedIntoNeo4j(data_type, f'{data_store}/{data_type}/{file_name}').feed_to_neo4j()
        elif data_type == 'Experiment':
            return FeedIntoNeo4j(data_type, f'{data_store}/{data_type}/{file_name}').feed_to_neo4j()
        else:
            return FeedIntoNeo4j(data_type, f'{data_store}/{data_type}/{file_name}').feed_to_neo4j()

    except Exception as e:
        return 'error'


UNIQUE_ID = {
    'PreData': 'Sample_ID',
    'PostData': 'Sample_ID',
    'Experiment': 'Experiment_ID',
    'Probe':'Unique_ID',
    'Versuch':'Unique_ID',
    'Process': 'Process_ID',
    'CPA': 'CPA_ID',
    'DSC': 'DSC_ID',
    'FTIR': 'FTIR_ID',
    'Cryomicroscopy': 'Cryomicroscopy_ID',
    'Osmolality': 'Osmolality_ID',
    'Viscosity': 'Viscosity_ID',
}


@app.get("/queryOneType/")
def queryOneType(data_type):
    query = f"MATCH (p:{data_type}) RETURN COLLECT(p.{UNIQUE_ID[data_type]}) AS idList"
    if data_type in ['PreData', 'PostData', 'Experiment']:
        result = GRAPH_CRYO.run(query).data()
    else:
        result = GRAPH_CPA.run(query).data()

    return str(sorted(result[0]['idList'])).replace("'", '"')


@app.get("/queryOneNode/")
def queryOneNode(data_type, ID):
    query = f'MATCH (p:{data_type}) WHERE p.{UNIQUE_ID[data_type]} = "{ID}" RETURN p'
    if data_type in ['PreData', 'PostData', 'Experiment']:
        result = GRAPH_CRYO.run(query).data()
    else:
        result = GRAPH_CPA.run(query).data()
    return result[0]['p']


@app.get("/duplicateCheck/")
def duplicateCheck(data_type, ID):
    query = f'MATCH (p:{data_type}) WHERE p.{UNIQUE_ID[data_type]} = "{ID}" RETURN COUNT(p) > 0'
    if data_type in ['PreData', 'PostData', 'Experiment']:
        result = GRAPH_CRYO.run(query).data()
    else:
        result = GRAPH_CPA.run(query).data()
    return result[0]["COUNT(p) > 0"]


@app.get("/queryOneExperiment/{ID}")
def queryOneExperiment(ID):
    query = f'MATCH(experiment: Experiment)\
              WHERE experiment.Experiment_ID = "{ID}"\
              OPTIONAL MATCH (experiment: Experiment)<-[:versuch_of_experiment]-(second: Versuch)\
              OPTIONAL MATCH (second)<-[:probe_of_versuch*..1]-(third:Probe)\
              WITH experiment, second, COLLECT(DISTINCT third) as thirdNodes\
              RETURN experiment, COLLECT({{versuch: second, probes: thirdNodes}}) as child'
    result = GRAPH_CRYO.run(query).data()[0]
    try:
        result['child'] = sorted(
            result['child'], key=lambda child: child['versuch']['Versuch_ID'])
    except:
        pass
    return result


@app.get("/queryOneCPA/{ID}")
def queryOneCPA(ID):
    query = f"""MATCH (cpa:CPA {{CPA_ID: '{ID}'}})\
              OPTIONAL MATCH (cpa:CPA {{CPA_ID: '{ID}'}})-[*..1]->(c)\
              WITH cpa, c,\
                CASE labels(c)[0]\
                    WHEN 'DSC' THEN c.DSC_ID\
                    WHEN 'FTIR' THEN c.FTIR_ID\
                    WHEN 'Cryomicroscopy' THEN c.Cryomicroscopy_ID\
                    WHEN 'Osmolality' THEN c.Osmolality_ID\
                    WHEN 'Viscosity' THEN c.Viscosity_ID\
                END AS attribute_value\
              RETURN cpa, COLLECT({{class: labels(c)[0], unique_id:attribute_value, properties: properties(c)}}) AS child"""
    result = GRAPH_CPA.run(query).data()[0]
    for child in result['child']:
        try:
            del child['properties']['Curve']
        except:
            continue
    return result


@app.post("/getMeanAndVariance/")
def getMeanAndVariance(req: Dict[Any, Any] = None):
    data = req['data']
    # data = urllib.parse.unquote(data)
    # data = ast.literal_eval(data)
    data = [float(item) for item in data]
    mean = np.mean(data)
    variance = np.var(data, ddof=1)
    standard_deviation = np.std(data, ddof=1)
    standard_error = standard_deviation / np.sqrt(len(data))
    confidence_level = 0.95
    n = len(data)
    confidence_interval = stats.t.interval(
        confidence_level, df=n-1, loc=mean, scale=standard_error)

    if n == 1:
        variance = standard_deviation = standard_error = 0.0000
        confidence_interval = (0.00, 0.00)
    return {
        "mean": f"{mean:.4f}",
        "variance": f"{variance:.4f}",
        "SD": f"{standard_deviation:.4f}",
        "SE": f"{standard_error:.4f}",
        f"CI {confidence_level * 100:.0f}%": f"[{confidence_interval[0]:.2f}, {confidence_interval[1]:.2f}]"
    }


@app.post("/buildColumn/")
def buildColumn(data: Dict[Any, Any] = None):
    predata, postdata, key = data['predata'], data['postdata'], data['key']
    # predata = urllib.parse.unquote(predata)
    # predata = ast.literal_eval(predata)
    # postdata = urllib.parse.unquote(postdata)
    # postdata = ast.literal_eval(postdata)

    query_pre = f"MATCH (n:PreData)\
              WHERE n.Sample_ID IN {str(predata)}\
              RETURN COLLECT(n.`{key}`) AS data"

    query_post = f"MATCH (n:PostData)\
              WHERE n.Sample_ID IN {str(postdata)}\
              RETURN COLLECT(n.`{key}`) AS data"

    result_pre = GRAPH_CRYO.run(query_pre).data()[0]['data']
    result_post = GRAPH_CRYO.run(query_post).data()[0]['data']

    return {
        "pre_data": getMeanAndVariance({'data': result_pre}),
        "post_data": getMeanAndVariance({'data': result_post}),
        "post/pre": getMeanAndVariance({'data': [f"{(float(item)*100)/float(np.mean([float(item) for item in result_pre])):.4f}" for item in result_post]})
    }


@app.post("/buildAnovaTable/")
def buildAnovaTable(data: Dict[Any, Any] = None):
    postdata, predata, key = data['postdata'], data['predata'], data['key']
    # postdata = urllib.parse.unquote(postdata)
    # postdata = ast.literal_eval(postdata)\\
    ppdata = {}
    for _key in list(postdata.keys()):
        su = []
        for i, p in enumerate(postdata[_key]):
            query_post = f"MATCH (n:PostData)\
                WHERE n.Sample_ID IN {str(p)}\
                RETURN COLLECT(n.`{key}`) AS data"
            query_pre = f"MATCH (n:PreData)\
                WHERE n.Sample_ID IN {str(predata[_key][i])}\
                RETURN COLLECT(n.`{key}`) AS data"
            postdata[_key][i] = GRAPH_CRYO.run(query_post).data()[0]['data']
            mean = np.mean(
                [float(item) for item in GRAPH_CRYO.run(query_pre).data()[0]['data']])
            su.append([str((float(item)*100)/mean)
                      for item in postdata[_key][i]])
        ppdata[_key] = su
    for _key in list(postdata.keys()):
        postdata[_key] = [item for sublist in postdata[_key]
                          for item in sublist]
        ppdata[_key] = [item for sublist in ppdata[_key] for item in sublist]

    return {
        "post": anovaTest(str(postdata)),
        "post/pre": anovaTest(str(ppdata))
    }


@app.get("/anovaTest/{daten}")
def anovaTest(daten):
    daten = urllib.parse.unquote(daten)
    daten = ast.literal_eval(daten)
    # data_dict = ast.literal_eval(data_str)
    # print(data_dict)
    keys = list(daten.keys())
    data = list(daten.values())

    result = {}

    # ANOVA
    f_statistic, p_value = f_oneway(*data)

    result["F-statistic"] = round(f_statistic, 4)
    result["p-value"] = round(p_value, 4)
    # Tukey's HSD
    tukey_results = pairwise_tukeyhsd([float(n) for n in np.concatenate(
        data)], np.repeat(keys, [len(d) for d in data]), 0.05)
    df = pandas.DataFrame(
        data=tukey_results._results_table.data[1:], columns=tukey_results._results_table.data[0])
    result["Tukey HSD 0.05"] = list(df.to_dict(orient='index').values())
    result['Tukey Group'] = generate_tukey_subscripts(df)
    return result


def generate_tukey_subscripts(tukey_result_df):

    all_groups = list(set(tukey_result_df["group1"]).union(
        set(tukey_result_df["group2"])))
    gmeans = {}
    gmeans[all_groups[0]] = 0

    related_comparisons = tukey_result_df[(
        tukey_result_df["group1"] == all_groups[0])]
    related_comparisons_2 = tukey_result_df[(
        tukey_result_df["group2"] == all_groups[0])]

    for _, comparison in related_comparisons.iterrows():
        gmeans[comparison["group2"]] = 0 + comparison['meandiff']
    for _, comparison in related_comparisons_2.iterrows():
        gmeans[comparison["group1"]] = 0 - comparison['meandiff']

    sorted_groups = sorted(all_groups, key=lambda group: -gmeans[group])

    result_group = {}
    for group in sorted_groups:
        result_group[group] = ''
    letters = [chr(i) for i in range(ord('a'), ord('z')+1)]
    index = 0

    for i in range(len(sorted_groups)):
        result_group[sorted_groups[i]] += letters[index]
        for j in range(len(sorted_groups)):
            if i != j:
                # p_value = tukey_result_df[(tukey_result_df["group1"] == sorted_groups[i]) & (tukey_result_df["group2"] == sorted_groups[j]) |(tukey_result_df["group2"] == sorted_groups[i]) & (tukey_result_df["group1"] == sorted_groups[j])]['p-adj'].iloc[0]
                p_value = tukey_result_df.loc[
                    ((tukey_result_df["group1"] == sorted_groups[i]) & (tukey_result_df["group2"] == sorted_groups[j])) | (
                        (tukey_result_df["group2"] == sorted_groups[i]) & (tukey_result_df["group1"] == sorted_groups[j])),
                    "p-adj"
                ].iloc[0]
                if p_value <= 0.05:
                    if p_value <= 0.01:
                        result_group[sorted_groups[j]
                                     ] += letters[index].upper()
                    else:
                        result_group[sorted_groups[j]] += letters[index]
        if any(value == '' for value in result_group.values()):
            index += 1
        else:
            break

    return result_group


@app.get("/tTest/")
def tTest(data1, data2, alpha=0.05):
    t_statistic, p_value = ttest_ind(data1, data2)

    is_significant = p_value < alpha

    return {
        "t_statistic": t_statistic,
        "p_value": p_value,
        "is_significant": is_significant
    }


@app.post("/addDelModi/")
def addDelModi(todoSQL: Dict[Any, Any] = None):
    addition, deletion, changeAttr, changeName = todoSQL['addition'], todoSQL['deletion'], todoSQL['changeAttr'], todoSQL['changeName']
    result = {
        'addition': [],
        'deletion': {'nodeAttributes':[], 'childrenNodes': [], 'fatherNodes':[]},
        'changeName': {},
        'changeAttr':{}
    }
    for todo in addition:
        if todo['class'] == 'Versuch':
            graph = GRAPH_CRYO
            versuch_node = Node('Versuch', Versuch_ID=todo["info"]["Versuche ID"],
                                Unique_ID=f'{todo["father"]["Unique_ID"]}*-*{todo["info"]["Versuche ID"]}')

            experiment_node = graph.nodes.match(
                'Experiment', Experiment_ID=todo['father']['Unique_ID']).first()
            graph.create(Relationship(
                versuch_node, 'versuch_of_experiment', experiment_node))
            for probe in list((todo['info']).keys())[1:]:
                probe_node = Node('Probe', **{k.replace(' ', '_'): str(v) if isinstance(v, dict) else v for k, v in todo['info'][probe].items(
                )}, Unique_ID=f"{todo['father']['Unique_ID']}*-*{todo['info']['Versuche ID']}*-*{todo['info'][probe]['Sample ID']}")

                versuch_node = graph.nodes.match(
                    'Versuch', Unique_ID=f'{todo["father"]["Unique_ID"]}*-*{todo["info"]["Versuche ID"]}').first()
                graph.create(Relationship(
                    probe_node, 'probe_of_versuch', versuch_node))
                for pre_id in todo['info'][probe]['PreData ID']:
                    predata_node = graph.nodes.match(
                        'PreData', Sample_ID=pre_id).first()
                    graph.create(Relationship(
                        predata_node, 'pre_data_of_probe', probe_node))
                for post_id in todo['info'][probe]['PostData ID']:
                    postdata_node = graph.nodes.match(
                        'PostData', Sample_ID=post_id).first()
                    graph.create(Relationship(
                        postdata_node, 'post_data_of_probe', probe_node))
            result['addition'].append('success')
        elif todo['class'] == 'Probe':
            graph = GRAPH_CRYO
            versuch_node = graph.nodes.match(
                'Versuch', Unique_ID=todo["father"]["Unique_ID"]).first()
            probe_node = Node('Probe', **{k.replace(' ', '_'): str(v) if isinstance(v, dict) else v for k, v in todo['info'].items(
            )}, Unique_ID=f"{todo['father']['Unique_ID']}*-*{todo['info']['Sample ID']}")
            graph.create(Relationship(
                probe_node, 'probe_of_versuch', versuch_node))
            for pre_id in todo['info']['PreData ID']:
                predata_node = graph.nodes.match(
                    'PreData', Sample_ID=pre_id).first()
                graph.create(Relationship(
                    predata_node, 'pre_data_of_probe', probe_node))
            for post_id in todo['info']['PostData ID']:
                postdata_node = graph.nodes.match(
                    'PostData', Sample_ID=post_id).first()
                graph.create(Relationship(
                    postdata_node, 'post_data_of_probe', probe_node))
            result['addition'].append('success')
        elif todo['class'] in ['PreData', 'PostData', 'Process']:
            graph = GRAPH_CRYO
            unique_name = 'Sample_ID' if todo['class'] != 'Process' else 'Process_ID'
            graph.run(f"""
                    MATCH (n: {todo['class']})
                    WHERE n.`{unique_name}` = "{todo['unique_id']}"
                    SET n.`{todo['attrKey']}` = "{todo['attrValue']}"
                """)
            result['addition'].append('success')
        else:
            graph = GRAPH_CPA
            if 'father' in list(todo.keys()):
                cpa_node = graph.nodes.match('CPA', CPA_ID=todo['father']['Unique_ID']).first()
                new_node = Node(todo['class'], **{k.replace(' ', '_'): str(v) if isinstance(v, dict) else v for k, v in todo['info'].items()})
                graph.create(Relationship(cpa_node, f"{todo['class']}_of_CPA", new_node))
                result['addition'].append('success')
            else:
                graph.run(f"""
                    MATCH (n: {todo['class']})
                    WHERE n.`{todo['class']}_ID` = "{todo['unique_id']}"
                    SET n.`{todo['attrKey']}` = "{todo['attrValue']}"
                """)
                result['addition'].append('success')

    for todo in deletion['nodeAttributes']:
        graph = GRAPH_CRYO if todo['nodeClass'] in ['PreData', 'PostData', 'Versuch', 'Experiment', 'Probe'] else GRAPH_CPA
        graph.run(f"""
                    MATCH (n: {todo['nodeClass']})
                    WHERE n.`{UNIQUE_ID[todo['nodeClass']] if todo['nodeClass'] in list(UNIQUE_ID.keys()) else (todo['nodeClass']+'_ID')}` = "{todo['Unique_ID']}"
                    REMOVE n.`{todo['attributeKey']}`
                """)
        result['deletion']['nodeAttributes'].append('success')
    for todo in deletion['childrenNodes']:
        if todo['nodeClass'] in ['PreData', 'PostData']:
            GRAPH_CRYO.run(f"""
                        MATCH (n: {todo['nodeClass']})
                        WHERE n.Sample_ID = "{todo['Unique_ID']}"
                        OPTIONAL MATCH (n)--(p:Probe)
                        DETACH DELETE n
                        SET p.`{todo['nodeClass']}_ID` = [id IN p.{todo['nodeClass']}_ID WHERE id <> "{todo['Unique_ID']}"]
                    """)
            result['deletion']['nodeAttributes'].append('success')
        elif todo['nodeClass'] == 'Process':
            GRAPH_CPA.run(f"""
                        MATCH (n: Process)
                        WHERE n.Process_ID = "{todo['Unique_ID']}"
                        DETACH DELETE n
                    """)
            result['deletion']['nodeAttributes'].append('success')
        else:
            GRAPH_CPA.run(f"""
                        MATCH (n: {todo['nodeClass']})
                        WHERE n.`{todo['nodeClass']}_ID` = "{todo['Unique_ID']}"
                        DETACH DELETE n
                    """)
            result['deletion']['nodeAttributes'].append('success')

    for todo in deletion['fatherNodes']:
        if todo['nodeClass'] == 'Versuch':
            GRAPH_CRYO.run(f"""
                        MATCH (n: Versuch)
                        WHERE n.Unique_ID = "{todo['Unique_ID']}"
                        OPTIONAL MATCH (n)--(p:Probe)
                        DETACH DELETE n, p
                    """)
            result['deletion']['nodeAttributes'].append('success')
        elif todo['nodeClass'] == 'Experiment':
            GRAPH_CRYO.run(f"""
                        MATCH (e: Experiment)
                        WHERE e.Experiment_ID = "{todo['Unique_ID']}"
                        OPTIONAL MATCH (e)--(v:Versuch)
                        OPTIONAL MATCH (v)--(p:Probe)
                        DETACH DELETE e, v, p
                    """)
            result['deletion']['nodeAttributes'].append('success')
        elif todo['nodeClass'] == 'Probe':
            GRAPH_CRYO.run(f"""
                        MATCH (n: Probe)
                        WHERE n.Unique_ID = "{todo['Unique_ID']}"
                        DETACH DELETE n
                    """)
            result['deletion']['nodeAttributes'].append('success')
        elif todo['nodeClass'] == 'CPA':
            GRAPH_CPA.run(f"""
                        MATCH (c: CPA)
                        WHERE c.CPA_ID = "{todo['Unique_ID']}"
                        OPTIONAL MATCH (c)--(i)
                        DETACH DELETE c, i
                    """)
            result['deletion']['nodeAttributes'].append('success')
    
    changeAttr = sorted(changeAttr, key=custom_sort_key)
    for todo in changeAttr:
        graph = GRAPH_CRYO if todo['class'] in ['PreData', 'PostData', 'Versuch', 'Experiment', 'Probe'] else GRAPH_CPA
        if todo['attrKey'] in ['PostData_ID', 'PreData_ID']:
            graph.run(f"""
                    MATCH (p: Probe)
                    WHERE p.Unique_ID = "{todo['unique_id']}"
                    SET p.`{todo['attrKey']}` = {todo['currentValue']}
                """)
            relation_type = 'pre_data_of_probe' if todo['attrKey']=='PreData_ID' else 'post_data_of_probe'
            graph.run(f"""
                    MATCH (p: Probe)-[r:{relation_type}]-()
                    WHERE p.Unique_ID = "{todo['unique_id']}"
                    DELETE r
                """)
            probe_node = graph.nodes.match('Probe', Unique_ID=todo['unique_id']).first()
            pp_type = 'PreData' if todo['attrKey']=='PreData_ID' else 'PostData'
            for data_id in todo['currentValue']:
                pp_node = graph.nodes.match(pp_type, Sample_ID=data_id).first()
                graph.create(Relationship(pp_node, relation_type, probe_node))
        else:
            graph.run(f"""
                    MATCH (p: {todo['class']})
                    WHERE p.`{UNIQUE_ID[todo['class']]}` = "{todo['unique_id']}"
                    SET p.`{todo['attrKey']}` = "{todo['currentValue']}"
                """)
        result['changeAttr'][todo['unique_id']] = 'success'

    changeName = sorted(changeName, key=custom_sort_key)
    for todo in changeName:
        if todo['class'] in ['PreData', 'PostData']:
            GRAPH_CRYO.run(f"""
                    MATCH (n:{todo['class']})
                    WHERE n.Sample_ID = "{todo['unique_id']}"
                    OPTIONAL MATCH (n)--(p:Probe)
                    SET n.Sample_ID = "{todo['currentName']}"
                    SET p.`{todo['class']}_ID` = [item IN p.{todo['class']}_ID | CASE WHEN item = "{todo['unique_id']}" THEN "{todo['currentName']}" ELSE item END]
                    """)
            result['changeName'][todo['unique_id']] = 'success'
        
        elif todo['class'] == 'Process':
            GRAPH_CPA.run(f"""
                    MATCH (n:{todo['class']})
                    WHERE n.Process_ID = "{todo['unique_id']}"
                    SET n.Process_ID = "{todo['currentName']}"
                    """)
            GRAPH_CRYO.run(f"""
                    MATCH (p:Probe)
                    WHERE p.Process_ID = "{todo['unique_id']}"
                    SET p.Process_ID = "{todo['currentName']}"
                    """)
            result['changeName'][todo['unique_id']] = 'success'

        elif todo['class'] == 'Probe':
            GRAPH_CRYO.run(f"""
                    MATCH (p:Probe)
                    WHERE p.Unique_ID = "{todo['unique_id']}"
                    SET p.Sample_ID = "{todo['currentName']}"
                    SET p.Unique_ID = "{todo['unique_id'].rsplit('*-*', 1)[0] + '*-*' + todo['currentName']}"
                    """)
            result['changeName'][todo['unique_id']] = 'success'

        elif todo['class'] == 'Versuch':
            GRAPH_CRYO.run(f"""
                    MATCH (v:Versuch)
                    WHERE v.Unique_ID = "{todo['unique_id']}"
                    SET v.Versuch_ID = "{todo['currentName']}"
                    SET v.Unique_ID = "{todo['unique_id'].rsplit('*-*', 1)[0] + '*-*' + todo['currentName']}"
                    """)
            GRAPH_CRYO.run(f"""
                    MATCH (v:Versuch)--(p:Probe)
                    WHERE v.Unique_ID = "{todo['unique_id'].rsplit('*-*', 1)[0] + '*-*' + todo['currentName']}"
                    WITH p, SPLIT(p.Unique_ID, '*-*') AS parts
                    WITH p, parts[0] + "*-*{todo['currentName']}*-*" + parts[2] AS new_uniqueId
                    SET p.Unique_ID = new_uniqueId
                    """)
            result['changeName'][todo['unique_id']] = 'success'

        elif todo['class'] == 'Experiment':
            GRAPH_CRYO.run(f"""
                    MATCH (e:Experiment)
                    WHERE e.Experiment_ID = "{todo['unique_id']}"
                    SET e.Experiment_ID = "{todo['currentName']}"
                    """)
            GRAPH_CRYO.run(f"""
                    MATCH (e:Experiment)--(v:Versuch)
                    WHERE e.Experiment_ID = "{todo['currentName']}"
                    WITH v, SPLIT(v.Unique_ID, '*-*') AS parts
                    WITH v, "{todo['currentName']}*-*" + parts[1] AS new_uniqueIdVersuch
                    SET v.Unique_ID = new_uniqueIdVersuch
                    """)
            GRAPH_CRYO.run(f"""
                    MATCH (e:Experiment)--()--(p:Probe)
                    WHERE e.Experiment_ID = "{todo['currentName']}"
                    WITH p, SPLIT(p.Unique_ID, '*-*') AS partsP
                    WITH p, "{todo['currentName']}*-*" + partsP[1] + "*-*" + partsP[2] AS new_uniqueId
                    SET p.Unique_ID = new_uniqueId
                    """)
            result['changeName'][todo['unique_id']] = 'success'
        elif todo['class'] == 'CPA':
            GRAPH_CPA.run(f"""
                    MATCH (n:CPA)
                    WHERE n.CPA_ID = "{todo['unique_id']}"
                    SET n.CPA_ID = "{todo['currentName']}"
                    """)
            GRAPH_CRYO.run(f"""
                    MATCH (p:Probe)
                    WHERE p.CPA_ID = "{todo['unique_id']}"
                    SET p.CPA_ID = "{todo['currentName']}"
                    """)
            result['changeName'][todo['unique_id']] = 'success'
        else:
            GRAPH_CPA.run(f"""
                    MATCH (n:{todo['class']})
                    WHERE n.`{todo['class']}_ID` = "{todo['unique_id']}"
                    SET n.`{todo['class']}_ID` = "{todo['currentName']}"
                    """)
            result['changeName'][todo['unique_id']] = 'success'

    return result


def custom_sort_key(input_item):
    item = input_item['class']
    if item == 'PreData':
        return (0, item)
    elif item == 'PostData':
        return (1, item)
    elif item == 'Process':
        return (2, item)
    elif item == 'Probe':
        return (4, item)
    elif item == 'Versuch':
        return (5, item)
    elif item == 'Experiment':
        return (6, item)
    elif item == 'CPA':
        return (7, item)
    else:
        return (3, item)
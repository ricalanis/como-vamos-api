import os
import requests
import Levenshtein
import pandas as pd
import csv
import json
import numpy as np
from pymongo import MongoClient
from math import isnan
import simplejson as json



DATADIRECTORY = "data"
OBJECTIVEDATA_STRING = "objetivo"
SUBJECTIVEDATA_STRING = "subjetivo"
OBJECTIVEDATA_VERBOSE = "indicadores"
SUBJECTIVEDATA_VERBOSE = "encuestas"
DICTIONARY_STRING = "diccionario"
DATA_STRING = "datos"


#Diccionario provisional de ciudades
cities = []
cities_pretty_name = {"bogota":"Bogotá", "cartagena":"Cartagena", "bucaramanga-metropolitana":"Bucaramanga Metropolitana", "cali":"Cali", "ibague": "Ibagué", "manizales": "Manizales", "medellin":"Medellín", "pereira":"Pereira", "valledupar":"Valledupar", "yumbo": "Yumbo"}
#cities_pretty_name = {"bogota":"Bogotá"}


def return_city_files(allcityfiles,city):
    cityfiles = []
    for filename in allcityfiles:
        if city in filename:
            cityfiles.append(filename)
    return(cityfiles)

def identify_data_type(cityfiles):
    datatype_byfilename = {}
    for filename in cityfiles:
        ratio_objective = Levenshtein.ratio(filename,OBJECTIVEDATA_VERBOSE)
        ratio_subjetive = Levenshtein.ratio(filename,SUBJECTIVEDATA_VERBOSE)
        if ratio_objective > ratio_subjetive:
            datatype = OBJECTIVEDATA_STRING
        else:
            datatype = SUBJECTIVEDATA_STRING
        if DICTIONARY_STRING in filename:
            filetype = DICTIONARY_STRING
        else:
            filetype = DATA_STRING
        datatype_byfilename[filename] = {"datatype":datatype,"filetype":filetype}
    return(datatype_byfilename)

def return_allcityfiles():
    allcityfiles = os.listdir(DATADIRECTORY)
    return allcityfiles

def get_data_type(files_data_type,type_string):
    dictionaries = {}
    for filename in files_data_type:
        if files_data_type[filename]["filetype"] == type_string:
            dictionaries[files_data_type[filename]["datatype"]] =filename
    return(dictionaries)

def dict_key_by_value(dict_to_search, value):
    for key in dict_to_search:
        if dict_to_search[key]==value:
            return key

def string_cleaner_for_dictionary(source_string):
    midstring_switch = str(source_string).replace("': '","MIDSTRINGSIGNAL")
    endstring_switch = midstring_switch.replace("', '", "ENDOFSTRINGSIGNAL")
    quote_removal = endstring_switch.replace("'","")
    double_quote_removal = quote_removal.replace('"',"")
    midstring_backinplace = double_quote_removal.replace("MIDSTRINGSIGNAL","': '")
    endstring_backinplace = midstring_backinplace.replace("ENDOFSTRINGSIGNAL","', '")
    doublequote_addition = "{'"+str(endstring_backinplace[1:-1])+"'}"
    switch_quote_type= doublequote_addition.replace("'",'"')
    return switch_quote_type

def extract_data_columns(year_string,variable_name,data_file):
    extracted_data = data_file[[year_string,variable_name]]
    extracted_data = extracted_data[pd.notnull(data_file[variable_name])]
    return extracted_data

def average_per_year(year_string, variable_name, filtered_data,data_type):
    data_return = []
    astype_data = filtered_data.convert_objects(convert_numeric=True)
    if data_type == "subjective":
        astype_data = astype_data[(astype_data[variable_name] >= 1.0) & (astype_data[variable_name]<=5.0)]
    ave_data = astype_data.groupby(year_string).mean()
    data_availability = ave_data[variable_name].keys()
    for key in data_availability:
        data_return.append({"year":int(key),"value":str(ave_data[variable_name][key])})
    return data_return

def responses_per_year(year_string, variable_name, filtered_data, responses_variable):
    data_return = []
    unique_years = pd.unique(filtered_data.AÑO.ravel())
    print(unique_years)
    for year in unique_years:
        yearly_sum = {}
        yearly_data = filtered_data[filtered_data[year_string]==year]
        yearly_responses = {}
        for i, year_indicator in yearly_data.iterrows():
            string_choices = year_indicator[variable_name]
            string_array_choices = string_choices.split(";")
            for choice in string_array_choices:
                if choice in yearly_responses:
                    yearly_responses[choice] = yearly_responses[choice] + 1
                else:
                    yearly_responses[choice] = 1

        for key in yearly_responses:
            try:
                yearly_sum[responses_variable[variable_name][key]] = str(yearly_responses[key])
            except:
                yearly_sum[key] = str(yearly_responses[key])
        data_return.append({"year":int(year),"value":str(yearly_sum)})
    return data_return

def extract_city_variableinfo(files_data_type,output_json,city,responses):
    dictionaries = get_data_type(files_data_type,DICTIONARY_STRING)
    objective_dictionary = pd.read_csv(DATADIRECTORY + "/" + dictionaries[OBJECTIVEDATA_STRING],delimiter=",", encoding="utf-8", dtype=np.string_ )
    subjective_dictionary = pd.read_csv(DATADIRECTORY + "/" + dictionaries[SUBJECTIVEDATA_STRING],delimiter=",", encoding="utf-8", dtype=np.string_ )

    output_json.append({"name":cities_pretty_name[city], "categories": []})
    output_json[-1]["categories"] = []

    rings = list(objective_dictionary.anillo.unique())

    for extra_ring in list(subjective_dictionary.dimension.unique()):
        if extra_ring not in rings:
            rings.append(extra_ring)

    category_position_index = {}
    for ring in rings:
        output_json[-1]["categories"].append({"name" : ring,"indicators" : []})
        category_position_index[ring] = len(output_json[-1]["categories"])-1

    ## Filling objective data
    for i, objective_dictionary_row in objective_dictionary.iterrows():
        if objective_dictionary_row["id"]==objective_dictionary_row["Indicador"]: next
        indicator_category = objective_dictionary_row["anillo"]
        category_position = category_position_index[indicator_category]
        current_indicator_data = {"name" : objective_dictionary_row["id"], "type":"objetivo", "description": objective_dictionary_row["Indicador"]}
        output_json[-1]["categories"][category_position_index[indicator_category]]["indicators"].append(current_indicator_data)

    responses_by_variable = {}
    for i, subjective_dictionary_row in subjective_dictionary.iterrows():
        if subjective_dictionary_row["variable"]==subjective_dictionary_row["descripcion"]: next
        indicator_category = subjective_dictionary_row["dimension"]
        category_position = category_position_index[indicator_category]
        if subjective_dictionary_row["tipo_respuestas"] == "ordinal":
            data_type = "subjetivo ordinal"
        else:
            data_type = "subjetivo categorico"
        current_indicator_data = {"name" : subjective_dictionary_row["variable"], "type":data_type, "description": subjective_dictionary_row["descripcion"]}
        output_json[-1]["categories"][category_position_index[indicator_category]]["indicators"].append(current_indicator_data)

        clean_response_string = string_cleaner_for_dictionary(subjective_dictionary_row["respuestas"])

        try:
            responses_by_variable[subjective_dictionary_row["variable"]] = json.loads(clean_response_string)
        except:
            responses_by_variable[subjective_dictionary_row["variable"]] = { "0": "NaN"}


    return output_json, responses_by_variable

def generate_city_data():
    client = MongoClient()
    db = client.test

    allcityfiles = return_allcityfiles()
    output_variable_json = []
    responses = {}
    for city in cities_pretty_name:
        print("Cargando Variables de " + city)
        city_files = return_city_files(allcityfiles,city)
        files_data_type =identify_data_type(city_files)
        output_variable_json, responses = extract_city_variableinfo(files_data_type,output_variable_json,city,responses)

    with open('cities.json', 'w') as fp:
        json.dump(output_variable_json, fp)

    with open ("cities.json", "r") as input_file:
        data=input_file.read().replace('NaN', '"NaN"')

    with open ("cities.json", "w") as fp:
        fp.write(data)


    allcityfiles = return_allcityfiles()
    for city_dictionary in output_variable_json:
        city_pretty = city_dictionary["name"]
        print("Cargando Variables de " + city_pretty)
        city_plain_name = dict_key_by_value(cities_pretty_name,city_pretty)

        city_files = return_city_files(allcityfiles,city_plain_name)
        files_data_type =identify_data_type(city_files)
        data_files = get_data_type(files_data_type,DATA_STRING)

        print(data_files)
        objective_data = pd.read_csv(DATADIRECTORY + "/" + data_files[OBJECTIVEDATA_STRING],delimiter=",", encoding="utf-8", dtype=np.string_ )
        subjective_data = pd.read_csv(DATADIRECTORY + "/" + data_files[SUBJECTIVEDATA_STRING],delimiter=",", encoding="utf-8", dtype=np.string_ )


        for category_data in city_dictionary["categories"]:
            for indicator_data in category_data["indicators"]:
                variable_name = indicator_data["name"]
                variable_type = indicator_data["type"]
                try:
                    if variable_type == "objetivo":
                        extracted_data = extract_data_columns("ANIO",variable_name,objective_data)
                        values = average_per_year("ANIO",variable_name,extracted_data,"objective")
                    elif variable_type == "subjetivo ordinal":
                        extracted_data = extract_data_columns("AÑO",variable_name,subjective_data)
                        values = average_per_year("AÑO",variable_name,extracted_data,"subjective")
                    else:
                        extracted_data = extract_data_columns("AÑO",variable_name,subjective_data)
                        values = responses_per_year("AÑO",variable_name,extracted_data,responses)
                except:
                        values = [{"year":int(2014),"value":[{"Caso especial de los datos": "0"}]}]
                return_dict = {"name":variable_name, "city":city_pretty, "type":variable_type, "value":values}
                db.test_cities.insert_one(return_dict)
    return "Success"

generate_city_data()
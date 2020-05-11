import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import pysal as ps
import shapely.wkt
import warnings
import pickle
import re
import time
import datetime
import json
import numpy as np
import geopandas as gpd
warnings.filterwarnings('ignore')
%matplotlib inline
from collections import defaultdict
import matplotlib.style
import matplotlib as mpl
mpl.style.use('seaborn-dark')
mpl.rcParams['figure.figsize'] = (15, 5)

def load_suffixes():

    suffixes = pd.read_csv('suffixes.txt',sep='\t')
    suffixes = suffixes.applymap(str.lower)
    suffixes = suffixes.applymap(str.strip)

    suffix_dict={}
    for x in range(suffixes.shape[0]):
        suffix_dict[suffixes.iloc[x,0]] = suffixes.iloc[x,1]
        suffix_dict[suffixes.iloc[x,1]] = suffixes.iloc[x,1]
        
    return suffix_dict

suffix_dict = load_suffixes()

def suffix(x):
    
    suffix = x.split(' ')[-1]
    notsuffix = x.split(' ')[:-1]
    if suffix in suffix_dict:
        suffix = suffix_dict[suffix]
    notsuffix.append(suffix)
    
    return ' '.join(notsuffix)

def replace_east_west_ordinal(x):
    
    e_pattern = re.compile("^east+?\s\d+")
    w_pattern = re.compile("^west+?\s\d+")
    if re.match(e_pattern,x) != None:
        x = x.replace('east','e')
    elif re.match(w_pattern,x) != None:
        x = x.replace('west','w')
        
    o_pattern = re.compile("(?<=[0-9])(?:st|nd|rd|th)")
    x = re.sub(o_pattern, '', x)
    
    return x

def load_parking_data(path,nrows):
    
    if nrows:
        raw = pd.read_csv(path,usecols=[0,23,24],nrows=nrows)
    else:
        raw = pd.read_csv(path,usecols=[0,23,24])
    raw['Street Name'] = raw['Street Name'].str.lower()
    raw = raw.dropna()
    raw['Street Name'] = raw['Street Name'].apply(suffix)
    raw['Street Name'] = raw['Street Name'].apply(replace_east_west_ordinal)
    
    return raw
    
def load_road_network():
    
    with open('addresses.json') as json_file:
        addresses = json.load(json_file)
        
    return addresses

def covert_to_json(parking):
    
    fines_dict=defaultdict(dict)

    for x in parking.index:

        streetname=parking.loc[x,'Street Name']
        housenumber=parking.loc[x,'House Number']
        finedex=parking.loc[x,'Summons Number']

        if housenumber not in fines_dict[streetname]:
             fines_dict[streetname][housenumber]=list()
        fines_dict[streetname][housenumber].append(str(finedex))
        
    import json
    with open('fines.json', 'w') as f:
        json.dump(fines_dict, f)

def match_location_writefile():
    
    """  """

    address_dict=load_road_network()
    fine_address={}
    with open('fines.json') as json_file:
        fines = json.load(json_file)

    for street in fines:
        
        if street in address_dict:

            ranges = address_dict[street]
            
            if 'nan_street' not in address_dict[street]:
            
                for h_num in fines[street]:

                    for rng in ranges:

                        low=rng[0]
                        high=rng[1]
                        road_dex=rng[2]
                        
                        if '-' not in h_num:
                            h_num = int(h_num)
                            low = int(low)
                            high = int(high)               

                        if (h_num >=low) and (h_num<=high):

                            for finedex in fines[street][h_num]:
                                fine_address[finedex]=road_dex
            else:
                fine_address[finedex]=np.random.choice(address_dict[street]['nan_street'])            
    
    with open('fine_adresses.csv','a') as a:
        for fine in fine_address:
            a.write(str(fine)+','+str(fine_address[fine])+'\n')
            
    return fine_address
            
def do_coordinate_matching(path,nrows=None):
    
    """Run this func with parking fine dataset as param.
    Approx 45-60 mins to finish matching one file.
    
    """
    
    print('\rProcess started at {}'.format(datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rLoading data..')
    parking = load_parking_data(path,nrows)
    print('\rParking data loaded..')
    print('\rGathering adresses...')
    covert_to_json(parking)
    print('\rJSON file created at {0}.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rMatching...')
    matched = match_location_writefile()
    year = path.split('.')[0].split('_')[-1]
    print('\Done matching year {} at {}'.format(year,datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rMatch performance: {} %'.format(len(matched)/parking.shape[0]*100))
    
def test():
    
    df = pd.read_csv('fine_adresses.csv')
    df.columns = ['fineID','roadID']
    
    rnd = np.random.randint(0,df.shape[0],size=1)
    finedex=int(df.loc[rnd,'fineID'])
    roaddex=int(df.loc[rnd,'roadID'])
    
    with open('coordinates.txt') as f:
        coords = [line.strip().split(';') for line in f]
    
    import folium
    import shapely.wkt

    def linestring_to_tuple(geometry,reverse=True):

        x_s = geometry.xy[0]
        y_s = geometry.xy[1]

        if reverse:
            return list(zip(y_s,x_s))
        else:
            return list(zip(x_s,y_s))

    P = shapely.wkt.loads(coords[int(rnd)][1])
    line=linestring_to_tuple(P)
    m = folium.Map()
    my_PolyLine=folium.PolyLine(locations=line,weight=5)
    m.add_children(my_PolyLine)
    
    print("Index: {}".format(finedex))
    
    return m
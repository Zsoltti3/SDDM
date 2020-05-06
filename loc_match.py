import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import pysal as ps
import shapely.wkt
import warnings
import pickle
import re
import time
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

def load_parking_data(path):
    
    raw = pd.read_csv(path,usecols=[0,23,24])
    raw['Street Name'] = raw['Street Name'].str.lower()
    raw = raw.dropna()
    raw['Street Name'] = raw['Street Name'].apply(suffix)
    raw['Street Name'] = raw['Street Name'].apply(replace_east_west_ordinal)
    
    return raw
    
def load_road_network(path):
    roadnetwork=pd.read_csv(path,index_col=0)
    return roadnetwork

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
        
def get_valid_adresses(roadnetwork):
    
    address_dict=defaultdict(list)
    nan_streets = roadnetwork[(roadnetwork['r_high_hn'].isna()) | (roadnetwork['r_low_hn'].isna()) | (roadnetwork['l_low_hn'].isna()) | (roadnetwork['l_high_hn'].isna())]['full_stree'].values

    for x in range(roadnetwork.shape[0]):

        streetname=roadnetwork.loc[x,'full_stree']

        if streetname not in nan_streets:

            address_dict[streetname].append(
                (roadnetwork.loc[x,'r_low_hn'],roadnetwork.loc[x,'r_high_hn'],x)
            )

            address_dict[streetname].append(
                (roadnetwork.loc[x,'l_low_hn'],roadnetwork.loc[x,'l_high_hn'],x)
        )
        if x%100000==0:
            print('\r{0}/{1}'.format(x,(roadnetwork.shape[0])))
            
    return address_dict, nan_streets

def match_location_writefile(roadnetwork):
    
    """  """

    address_dict, nan_streets=get_valid_adresses(roadnetwork)
    fine_address={}
    with open('fines.json') as json_file:
        fines = json.load(json_file)

    for street in fines:

        if street in address_dict:

            ranges = address_dict[street]
            
            for h_num in fines[street]:

                for rng in ranges:

                    low=rng[0]
                    high=rng[1]
                    road_dex=rng[2]

                    if (h_num >=low) and (h_num<=high):

                        for finedex in fines[street][h_num]:
                            fine_address[finedex]=road_dex

        elif street in nan_streets:

            fine_address[finedex]=np.random.choice(roadnetwork[roadnetwork['full_stree']==street].index)
            
    with open('fine_adresses.csv','w') as w:
        for fine in fine_address:
            w.write(str(fine)+','+str(fine_address[fine])+'\n')
            
def do_coordinate_matching(path):
    
    """Run this func with parking fine dataset as param.
    Approx 45-60 mins to finish matching one file.
    
    """
    
    print('\rProcess started at {}'.format(datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rLoading data..')
    parking = load_parking_data(path)
    print('\rParking data loaded..')
    roadnetwork = load_road_network('Road_.csv')
    print('\rRoad data loaded..')
    print('\rGathering adresses...')
    covert_to_json(parking)
    print('\rJSON file created at {0}.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rMatching...')
    match_location_writefile(roadnetwork)
    year = path.split('.')[0].split('_')[-1]
    print('\Done matching {} at {}'.format(year,datetime.datetime.now().strftime("%H:%M:%S")))
    df = pd.read_csv('fine_adresses.csv')
    print('\rMatch performance: {} %'.format(df.shape[0]/parking.shape[0]*100))
    
def test():
    
    df = pd.read_csv('fine_adresses.csv')
    df.columns = ['fineID','roadID']
    
    rnd = np.random.randint(0,df.shape[0],size=1)
    finedex=int(df.loc[rnd,'fineID'])
    roaddex=int(df.loc[rnd,'roadID'])
    parking.iloc[finedex,:]
    
    import folium
    import shapely.wkt

    def linestring_to_tuple(geometry,reverse=True):

        x_s = geometry.xy[0]
        y_s = geometry.xy[1]

        if reverse:
            return list(zip(y_s,x_s))
        else:
            return list(zip(x_s,y_s))

    P = shapely.wkt.loads(roadnetwork.loc[roaddex,'geometry'])
    line=linestring_to_tuple(P)
    m = folium.Map()
    my_PolyLine=folium.PolyLine(locations=line,weight=5)
    m.add_children(my_PolyLine)
    
    return m
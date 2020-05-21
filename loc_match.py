import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import pysal as ps
import shapely.wkt
import warnings
import pickle
import re
import os
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
    
    """ This one loads a file with the right suffixes use in the centerline data and fixes street names
    accordingly"""

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
    
    """ In centerline dataset 'West 56th street' is in a format of: 'w 56 st'.
    
    So get rid of ordinal ('th', 'nd') and transform 'west'-->'w', 'east'-->'e'
    """
    
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
    
    "Load actual year of fines and do transformations"
    
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
    
    """ Loads road_network (pre-processed form) from addresses.json  """  
    
    with open('addresses.json') as json_file:
        addresses = json.load(json_file)
        
    return addresses

def covert_to_json(parking):
    
    """ Might be unncesesary but it creates an intermediate json format of fines:
    
    {"street name":
        {"house number1":["index1","index2",etc]},
        {"house number2":["index1","index2",etc]}
    }
    
    """
    
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
        
def linestring_to_tuple(geometry,reverse=True):

    x_s = geometry.xy[0]
    y_s = geometry.xy[1]

    if reverse:
        return list(zip(y_s,x_s))
    else:
        return list(zip(x_s,y_s))
    
def point_to_tuple(geometry,reverse=True):
    
    x = geometry.x
    y = geometry.y
    
    if reverse:
        return (y,x)
    else:
        return (x,y)

def match_location_writefile():
    
    """ For every street-house number pair in fines data, chech if that number can be found in any address-range
    of that street in the centerline data
    
    if the number is present in any range --> good, match that road segment
    
    if the number is out of range (but the street name is matched) --> okay, match a random road segment of that street
    
    if street is not found --> bad, no match
    
    
    
    bookkeep.csv shoud track all choices for every fine 
    
    """

    bookkeep=dict()

    address_dict=load_road_network()
    fine_address={}
    with open('fines.json') as json_file:
        fines = json.load(json_file)

    for street in fines:

        if street in address_dict:

            ranges = address_dict[street]

            for h_num in fines[street]:

                matched = False

                for rng in ranges['ranges']:

                    low=rng[0]
                    high=rng[1]
                    road_dex=rng[2]

                    if (h_num >=low) and (h_num<=high):

                        matched = True

                        for finedex in fines[street][h_num]:
                            fine_address[finedex]=road_dex

                            bookkeep[finedex]='address_range'

                    if matched:
                        break

                    else:

                        if ranges['no_number']!=[]:

                            for finedex in fines[street][h_num]:
                                fine_address[finedex]=np.random.choice(ranges['no_number'])
                                bookkeep[finedex]='address_random_nan'
                        else:

                            for finedex in fines[street][h_num]:
                                fine_address[finedex]=np.random.choice([x[2] for x in ranges['ranges']])
                                bookkeep[finedex]='address_random_range'

        else:
            for x in fines[street]:
                for finedex in fines[street][x]:
                    bookkeep[finedex] = 'street_not_found'

    with open('fine_adresses.csv','a') as a:
            for fine in fine_address:
                a.write(str(fine)+','+str(fine_address[fine])+'\n')
                
    with open('bookkeep.csv','a') as a:
            for fine in bookkeep:
                a.write(str(fine)+','+str(bookkeep[fine])+'\n')

    return fine_address
            
def do_coordinate_matching(path,nrows=None):
    
    """ if you want all data to be matched, delete existing csv files, otherwise it will append to existing  """
    
    if not os.path.exists('fine_adresses.csv'):     
        with open('fine_adresses.csv','w') as w:
            pass
        
    if not os.path.exists('bookkeep.csv'):     
        with open('fine_adresses.csv','w') as w:
            pass
    
    """Run this func with parking fine dataset as param.
    Approx 4 hours to finish matching one file.
    
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
    print('\rDone matching year {} at {}'.format(year,datetime.datetime.now().strftime("%H:%M:%S")))
    print('\rMatch performance: {} %'.format(len(matched)/parking.shape[0]*100))
    
def test(check_original=False,path=None):
    
    """  When matching done, run it to select a random match and check it on map if it's correct.
    
    set check_original to TRUE if you want to see original addresses but then put the right path (original fine data)
    YOU WILL NEED centerline in a shapefile form: https://data.cityofnewyork.us/City-Government/NYC-Street-Centerline-CSCL-/exjm-f27b
    """
    
    print('Selecting random match...')
    df = pd.read_csv('fine_adresses.csv')
    df.columns = ['fineID','roadID']

    rnd = np.random.randint(0,df.shape[0],size=1)
    finedex=int(df.loc[rnd,'fineID'])
    roaddex=int(df.loc[rnd,'roadID'])

    coords = pd.read_csv('coordinates.txt')
    bookkeep=pd.read_csv('bookkeep.csv',header=None)

    print('Selected random fine: {}'.format(finedex))
    print('Matched road ID: {}'.format(roaddex))
    print('Join made by: {}'.format(
       bookkeep[bookkeep[0]==finedex][1].values[0]))

    import folium
    import shapely.wkt

    def linestring_to_tuple(geometry,reverse=True):

        x_s = geometry.xy[0]
        y_s = geometry.xy[1]

        if reverse:
            return list(zip(y_s,x_s))
        else:
            return list(zip(x_s,y_s))

    P = shapely.wkt.loads(coords[coords.physicalid==roaddex].geometry.values[0])
    line=linestring_to_tuple(P)
    m = folium.Map()
    my_PolyLine=folium.PolyLine(locations=line,weight=5)
    m.add_child(my_PolyLine)

    check_original=True
    if check_original:
        print('Checking for original street names...')
        with open(path) as f:
            f.readline()
            for line in f:
                sum_num = line.strip().split(',')[0]
                st_name = line.strip().split(',')[24]
                if sum_num==str(finedex):
                    print('Original street name (FINE): {}'.format(st_name))
                    break

        centerline = gpd.read_file('centerline.shp')
        print('Original street name (CENTERLINE): {}'.format(
            centerline[centerline.physicalid==roaddex].full_stree.values[0]))
        
    return m
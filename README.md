# SDDM
Run "do_coordinate_matching()" function in loc_match.py with a path to one of these '.csv' files:
https://data.cityofnewyork.us/City-Government/Parking-Violations-Issued-Fiscal-Year-2020/pvqr-7yc4


Fines are indexed by Summon number (unique).
Road segments are indexed by physicalid and can be found in coordinates.txt in a form of:
"physicalid,coordinates"

During matching, the street names from the Centerline data are loaded from addresses.json in a pre-processed form.

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPoint
from shapely.ops import split, unary_union
import osmnx as ox

pd.set_option("display.precision", 3)

from .clean import duplicate_nodes, correct_edges, clean_network
from .load import obtain_nodes_gdf, join_by_coordinates
from .utilities import distance_geometry_gdf

clean_settings = {'remove_disconnected_islands' : False, 'dead_ends' : False, 'same_uv_edges' : False, 'self_loops' : True, 'fix_topology' : False}

def get_urban_rail_fromOSM(place, download_method, epsg, distance = 7000): 
    """
    The function downloads and creates a simplified OSMNx graph for a selected area's urban rail network. 
    Afterwards, GeoDataFrames for nodes and edges are created, assigning new nodeID and edgeID identifiers.
        
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data. When 'polygon' the shape to get network data within. coordinates should be in
        unprojected latitude-longitude degrees (EPSG:4326).
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
    distance: float
        it is used only if download_method == "distance from address"
        
    Returns
    -------
    nodes_gdf, edges_gdf: Tuple of GeoDataFrames
        the nodes and edges GeoDataFrames
    """
    
    crs = 'EPSG:' + str(epsg)
    tag = {'railway' : True}  
    
    if download_method == 'distance_from_address': 
        railways_gdf = ox.geometries_from_address(place, tags = tag, dist = distance)
    elif download_method == 'OSMplace': 
        railways_gdf = ox.geometries_from_place(place, tags = tag)
    else: 
        railways_gdf = ox.geometries_from_polygon(place, tags = tag)
    
    print(railways_gdf.columns)
    railways_gdf = railways_gdf.to_crs(crs)
    to_keep = ["rail", "light_rail", "subway"]
    railways_gdf = railways_gdf[railways_gdf.railway.isin(to_keep)]
    railways_gdf['type'] = railways_gdf['railway']
    
    railways_gdf['length'] = railways_gdf.geometry.length
    railways_gdf = railways_gdf[["geometry", "length", "name", "type", "bridge", "tunnel"]]
    railways_gdf.reset_index(inplace=True, drop=True)
    railways_gdf['edgeID'] = railways_gdf.index.values.astype(int)
    railways_gdf.index.name = None
    return railways_gdf


def gdfs_from_railways(railways_gdf, epsg):  
    """
    The function loads a vector lines shapefile from a specified directory, along with the epsg coordinate code.
    It creates two GeoDataFrame, one for street junctions (nodes) and one for street segments (edges).
    The GeoDataFrames are built assuming a planar undirected graph. 
    The "case_study_area" polygon is optional and when provided is used to select geometries within the area + a buffer of x meters, fixed by the researcher (distance_from_boundary)
     
    Parameters
    ----------
    path: string
        the local path where the .shp file is stored
    epsg: int
        epsg of the area considered 
    dict_columns: dict
        it should be structured as: {"roadType_field": "highway",  "direction_field": "oneway", "nr. lanes": "lanes", "speed_field": None, "name_field": "name"}
        Replace the items with the field names in the input data (if the relative attributes are relevant and existing)

    Returns
    -------
    tuple of GeoDataFrames
    """
    
    crs = 'EPSG:' + str(epsg)
    # try reading street network from directory
    edges_gdf = railways_gdf.copy()
    edges_gdf["from"] = None
    edges_gdf["to"] = None
    edges_gdf["key"] = 0
    
    # creating the dataframes
    geometries = edges_gdf['geometry'].apply(lambda geom: geom.wkb)
    edges_gdf = edges_gdf.loc[geometries.drop_duplicates().index]
    
    standard_columns = ["geometry", "from", "to", "key", "name"]
    edges_gdf = edges_gdf[standard_columns]
    edges_gdf['code'], edges_gdf['coords'] = None, None

    # remove z coordinates, if any
    edges_gdf["geometry"] = edges_gdf.apply(lambda row: LineString([coor for coor in [row["geometry"].coords[i][0:2] for i in range(0, len(row["geometry"].coords))]]), axis = 1)
    
    # assigning indexes
    nodes_gdf = obtain_nodes_gdf(edges_gdf, crs)
    
    # linking on coordinates
    nodes_gdf["nodeID"] = nodes_gdf.index.values.astype(int)
    nodes_gdf, edges_gdf = join_by_coordinates(nodes_gdf, edges_gdf)
    edges_gdf.reset_index(inplace = True, drop = True)
    edges_gdf["edgeID"] = edges_gdf.index.values.astype(int)
    nodes_gdf.index.name = None
    edges_gdf.index.name = None
    
    # Assigning codes based on the edge's nodes. 
    # The string is formulated putting the node with lower ID first, regardless it being 'u' or 'v'
    edges_gdf["code"] = np.where(edges_gdf['v'] >= edges_gdf['u'], edges_gdf.u.astype(str)+"-"+edges_gdf.v.astype(str), edges_gdf.v.astype(str)+"-"+edges_gdf.u.astype(str))
    
    # Reordering coordinates to allow for comparison between edges
    nodes_gdf, edges_gdf = duplicate_nodes(nodes_gdf, edges_gdf)
    edges_gdf['coords'] = [list(c.coords) for c in edges_gdf.geometry]
    edges_gdf['coords'][(edges_gdf.u.astype(str)+"-"+edges_gdf.v.astype(str)) != edges_gdf.code] = [list(x.coords)[::-1] for x in edges_gdf.geometry]
    
    # dropping edges with same geometry but with coords in different orders (depending on their directions)    
    edges_gdf['tmp'] = edges_gdf['coords'].apply(tuple, 1)  
    edges_gdf.drop_duplicates(['tmp'], keep = 'first', inplace = True)
    #eliminate node-lines
    edges_gdf = edges_gdf[~((edges_gdf['u'] == edges_gdf['v']) & (edges_gdf['geometry'].length < 1.00))]     
    edges_gdf.drop(['coords', 'code', 'tmp'], axis = 1, inplace = True, errors = 'ignore')
    
    return nodes_gdf, edges_gdf
    
    
def assign_stations_to_nodes(stations_gdf, nodes_gdf, edges_gdf, name_field):
    
    nodes_gdf, edges_gdf = nodes_gdf.copy(), edges_gdf.copy()
    nodes_gdf['stationID'] = 999999
    nodes_gdf['name'] = None
               
    for row in stations_gdf.itertuples():

        station_geometry = stations_gdf.loc[row.Index].geometry
        
        dist_nodes = distance_geometry_gdf(station_geometry, nodes_gdf)
        dist_edges = distance_geometry_gdf(station_geometry, edges_gdf)
            
        if (dist_nodes[0]> 50) & (dist_edges[0]>50):
            continue
        elif (dist_nodes[0] <= dist_edges[0]):
            nodes_gdf.at[dist_nodes[1], 'stationID'] = row.Index
            nodes_gdf.at[dist_nodes[1], 'name'] = stations_gdf.loc[row.Index][name_field]
        else:
            index_edge = dist_edges[1]
            lines, point = split_line_at_interpolation(station_geometry, edges_gdf.loc[index_edge].geometry)
            nodeID = nodes_gdf.index.max()+1
            
            nodes_gdf.at[nodeID, 'geometry'] = point
            nodes_gdf.at[nodeID, 'nodeID'] = nodeID
            nodes_gdf.at[nodeID, 'stationID'] = row.Index
            nodes_gdf.at[nodeID, 'name'] = stations_gdf.loc[row.Index][name_field]
            
            new_index = edges_gdf.index.max()+1
            edges_gdf.loc[new_index] = edges_gdf.loc[index_edge]
            edges_gdf.at[index_edge, 'geometry'] =  lines[0]
            edges_gdf.at[index_edge, 'v'] = nodeID
            
            edges_gdf.at[new_index, 'geometry'] = lines[1]
            edges_gdf.at[new_index, 'edgeID'] = new_index
            edges_gdf.at[new_index, 'u'] = nodeID
               
    nodes_gdf['stationID'] = nodes_gdf['stationID'].astype(int)
    nodes_gdf['nodeID'] = nodes_gdf['nodeID'].astype(int)
    
    nodes_gdf.index = nodes_gdf['nodeID'].astype(int)
    nodes_gdf.index.name = None        
    nodes_gdf['x'], nodes_gdf['y'] = list(zip(*[(r.coords[0][0], r.coords[0][1]) for r in nodes_gdf.geometry]))
    edges_gdf = correct_edges(nodes_gdf, edges_gdf )
    
    return nodes_gdf, edges_gdf
    
def dissolve_stations(nodes_gdf, edges_gdf):
   
    nodes_gdf, edges_gdf = nodes_gdf.copy(), edges_gdf.copy()
    nodes_gdf, edges_gdf = simplify_stations(nodes_gdf, edges_gdf)
    nodes_gdf, edges_gdf = merge_station_nodes(nodes_gdf, edges_gdf)
    nodes_gdf, edges_gdf = simplify_stations(nodes_gdf, edges_gdf)   
    return nodes_gdf, edges_gdf
    
def simplify_stations(nodes_gdf, edges_gdf):
        # same station is at u and v of an edge
    nodes_gdf, edges_gdf = nodes_gdf.copy(), edges_gdf.copy()
    to_drop = []
    for row in edges_gdf.itertuples():
        u,v  = edges_gdf.loc[row.Index].u, edges_gdf.loc[row.Index].v

        if (nodes_gdf.loc[u]['name'] == nodes_gdf.loc[v]['name']) & (nodes_gdf.loc[u]['name'] is not None):
            edges_gdf.loc[edges_gdf.u == v, 'u'] = u
            edges_gdf.loc[edges_gdf.v == v, 'v'] = u
            centroid = nodes_gdf.loc[[u,v]].geometry.unary_union.centroid
            nodes_gdf.at[u, 'geometry'] = centroid
            to_drop.append(v)

    nodes_gdf.drop(to_drop, axis = 0, inplace = True)
    edges_gdf = edges_gdf[~((edges_gdf.u.isin(to_drop)) & (edges_gdf.v.isin(to_drop)))]
    nodes_gdf['x'], nodes_gdf['y'] = list(zip(*[(r.coords[0][0], r.coords[0][1]) for r in nodes_gdf.geometry]))
    edges_gdf = correct_edges(nodes_gdf, edges_gdf)
    nodes_gdf['nodeID'] = nodes_gdf['nodeID'].astype(int)
    nodes_gdf, edges_gdf = clean_network(nodes_gdf, edges_gdf, **clean_settings)

    return nodes_gdf, edges_gdf
    
    
def merge_station_nodes(nodes_gdf, edges_gdf, tolerance = 40):
    
    nodes_gdf, edges_gdf = nodes_gdf.copy(), edges_gdf.copy()
    to_drop = []
    old_edges_gdf = edges_gdf.copy()

    for row in old_edges_gdf.itertuples():
        u,v  = old_edges_gdf.loc[row.Index].u, old_edges_gdf.loc[row.Index].v
        if old_edges_gdf.loc[row.Index].geometry.length > tolerance:
            continue

        if ((nodes_gdf.loc[u]['stationID'] != nodes_gdf.loc[v]['stationID']) & 
             ((nodes_gdf.loc[u]['stationID'] == 999999) | (nodes_gdf.loc[v]['stationID'] == 999999))):

            if nodes_gdf.loc[u]['stationID'] != 999999: 
                nodeID = u
                drop = v
            else: 
                nodeID = v
                drop = u

            centroid = nodes_gdf.loc[[u,v]].geometry.unary_union.centroid
            nodes_gdf.at[nodeID, 'geometry'] = centroid
            edges_gdf.loc[edges_gdf.u == drop, 'u'] = nodeID
            edges_gdf.loc[edges_gdf.v == drop, 'v'] = nodeID
            to_drop.append(drop)

    nodes_gdf.drop(to_drop, axis = 0, inplace = True)
    edges_gdf = edges_gdf[~((edges_gdf.u.isin(to_drop)) & (edges_gdf.v.isin(to_drop)))]
    nodes_gdf['x'], nodes_gdf['y'] = list(zip(*[(r.coords[0][0], r.coords[0][1]) for r in nodes_gdf.geometry]))
    edges_gdf = correct_edges(nodes_gdf, edges_gdf)
    nodes_gdf['nodeID'] = nodes_gdf['nodeID'].astype(int)
    nodes_gdf, edges_gdf = clean_network(nodes_gdf, edges_gdf, **clean_settings)

    return nodes_gdf, edges_gdf
    
def extend_stations(nodes_gdf, edges_gdf):
    
    nodes_gdf, edges_gdf = nodes_gdf.copy(), edges_gdf.copy()
    tmp_nodes = nodes_gdf[nodes_gdf.stationID != 999999]
    
    for row in tmp_nodes.itertuples():
        tmp_edges = edges_gdf[edges_gdf.intersects(tmp_nodes.loc[row.Index].geometry.buffer(25))]
        tmp_edges = tmp_edges[(tmp_edges.u != row.Index) & (tmp_edges.v != row.Index)]
        if len(tmp_edges) == 0: 
            continue
        for e in tmp_edges.itertuples():
            lines, point = split_line_at_interpolation(tmp_nodes.loc[row.Index].geometry, edges_gdf.loc[e.Index].geometry)
            
            # check if there's actually another station already around
            if (point.distance(tmp_nodes.loc[row.Index].geometry) > 
               distance_geometry_gdf(point, nodes_gdf[(nodes_gdf.stationID != 999999) & (nodes_gdf.nodeID != row.Index)])[0]):
                continue
                
            station_u = nodes_gdf.loc[edges_gdf.loc[e.Index].u]['name']
            station_v  = nodes_gdf.loc[edges_gdf.loc[e.Index].v]['name']
            if ((station_u == nodes_gdf.loc[row.Index]['name']) | 
                (station_v == nodes_gdf.loc[row.Index]['name'])): continue
                    
            nodes_gdf.at[row.Index, 'geometry'] = MultiPoint([tmp_nodes.loc[row.Index].geometry.coords[0], point.coords[0]]).centroid
            new_index = edges_gdf.index.max()+1
            edges_gdf.loc[new_index] = edges_gdf.loc[e.Index]
            edges_gdf.at[e.Index, 'geometry'] =  lines[0]
            edges_gdf.at[e.Index, 'v'] = row.Index
            
            edges_gdf.at[new_index, 'geometry'] = lines[1]
            edges_gdf.at[new_index, 'edgeID'] = new_index
            edges_gdf.at[new_index, 'u'] = row.Index
    
    nodes_gdf['x'], nodes_gdf['y'] = list(zip(*[(r.coords[0][0], r.coords[0][1]) for r in nodes_gdf.geometry]))
    edges_gdf = correct_edges(nodes_gdf, edges_gdf)
    
    local_settings = clean_settings.copy()
    local_settings['same_uv_edges'] = True
    nodes_gdf, edges_gdf = clean_network(nodes_gdf, edges_gdf, **local_settings) 
    nodes_gdf, edges_gdf = dissolve_stations(nodes_gdf, edges_gdf)
    
    return nodes_gdf, edges_gdf
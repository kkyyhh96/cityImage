import osmnx as ox
import pandas as pd
import numpy as np
import geopandas as gpd

from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString
from shapely.ops import cascaded_union, linemerge, polygonize, polygonize_full, unary_union, nearest_points
pd.set_option("precision", 10)

def road_barriers(place, download_method, distance = None, epsg = None, include_primary = False):
    """
    The function downloads major roads from OSM. These can be considered to be barrier to pedestrian movement or, at least, to structure people's cognitive Image of the City.
    if 'include_primary' considers also primary roads, beyond motorway and trunk roads.
        
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string, {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data.
    distance: float
        it is used only if download_method == "distance from address"
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
    include_primary: boolean
        it is used only if download_method_graphB == "distance from address"
        
    Returns
    -------
    road_barriers: LineString GeoDataFrame
        the road barriers
    """
    
    crs = {'EPSG:' + str(epsg)}
    
    if download_method == 'distance_from_address': 
        roads_graph = ox.geometries_from_address(place, network_type = 'drive', distance = distance)
    elif download_method == 'OSMplace':
        roads_graph = ox.geometries_from_place(place, network_type = 'drive')
    else:
        roads_graph = ox.geometries_from_polygon(place, network_type = 'drive')
    
    roads = ox.graph_to_gdfs(roads_graph, nodes=False, edges=True, node_geometry= False, fill_edge_geometry=True)
    roads = roads.to_crs(crs)
    # exclude tunnels
    if "tunnel" in roads.columns:
        roads["tunnel"].fillna(0, inplace = True)
        roads = roads[roads["tunnel"] == 0] 
    
    # resolving lists 
    roads["highway"] = [x[0] if isinstance(x, list) else x for x in roads["highway"]]        
    roads.drop(['osmid', 'oneway', 'bridge', 'tunnel'], axis = 1, inplace = True, errors = 'ignore')
    main_types = ['trunk', 'motorway']
    if include_primary: 
        main_types = ['trunk', 'motorway', 'primary']
    roads = roads[roads.highway.isin(main_types)]
    roads = roads.unary_union
    
    if roads.type != "LineString": 
        roads = linemerge(roads)
        if roads.type != "LineString": 
            features = [i for i in roads]
        else: 
            features = [roads]
    else: 
        features = [roads]
    
    features = [i for i in roads]
    df = pd.DataFrame({'geometry': features, 'type': ['road'] * len(features)})
    road_barriers = gpd.GeoDataFrame(df, geometry = df['geometry'], crs = crs)
    road_barriers["from"] = road_barriers.apply(lambda row: row.geometry.coords[0], axis = 1)
    road_barriers["to"] = road_barriers.apply(lambda row: row.geometry.coords[-1], axis = 1)

    dd_u = dict(road_barriers['from'].value_counts())
    dd_v = dict(road_barriers['to'].value_counts())
    dd = {k: dd_u.get(k, 0) + dd_v.get(k, 0) for k in set(dd_u) | set(dd_v)}
    to_ignore = {k: v for k, v in dd.items() if v == 1}
    
    # exclude short sectors which are probably not continuous enough to be considered barriers
    road_barriers = road_barriers[~((road_barriers['from'].isin(to_ignore) & road_barriers['to'].isin(to_ignore)) & (road_barriers.length < 500))]
    road_barriers = road_barriers[~((road_barriers['from'].isin(to_ignore) | road_barriers['to'].isin(to_ignore)) & (road_barriers.length < 200))]
    road_barriers.drop(['from', 'to'], axis = 1, inplace = True)
    
    return road_barriers


def water_barriers(place, download_method, distance = None, epsg = None):
    """
    The function downloads water bodies from OSM. Lakes, rivers and see coastlines can be considered structuring barriers.
        
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data.
    distance: float
        it is used only if download_method == "distance from address"
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
        
    Returns
    -------
    water_barriers: LineString GeoDataFrame
        the water barriers GeoDataFrame
    """
    
    crs = {'EPSG:' + str(epsg)}
    
    # rivers and canals
    tag = {"waterway":"river", "waterway":"canal"}  
    rivers = _download_geometries(place, download_method, tag, crs}
    if "tunnel" in rivers.columns:
        rivers["tunnel"].fillna(0, inplace = True)
        rivers = rivers[rivers["tunnel"] == 0] 
    rivers = rivers.unary_union
    
    to_remove = {"natural":"water", "water":"river", "water":"steam"}   
    possible_duplicates = _download_geometries(place, download_method, to_remove, crs}
    pd = possible_duplicates.unary_union
    rivers = rivers.difference(pd)
    rivers = _simplify_barrier(river)
    rivers = _create_gdf(rivers, crs)
    
    # lakes   
    tag = {"natural":"water"}
    lakes = _download_geometries(place, download_method, tag, crs}                     
    lakes = lakes.unary_union
    
    to_remove = {"water":"river", "waterway": True, "water":"steam"}   
    possible_duplicates = _download_geometries(place, download_method, to_remove, crs}
    pd = possible_duplicates.unary_union
    lakes = lakes.difference(pd)
    lakes = _simplify_barrier(lakes) 
    lakes = _create_gdf(lakes, crs)
    lakes = lakes[lakes['length'] >=500]
    
    # sea   
    tag = {"natural":"coastline"}
    lakes = _download_geometries(place, download_method, tag, crs)
    sea = sea.unary_union      
    sea = _simplify_barrier(sea)
    sea = _create_gdf(sea, crs)
    
    water = rivers.append(lakes)
    water = water.append(sea)
    water = water.unary_union
    water = _simplify_barrier(water)
        
    df = pd.DataFrame({'geometry': features, 'type': ['water'] * len(features)})
    water_barriers = gpd.GeoDataFrame(df, geometry = df['geometry'], crs = crs)
    
    return water_barriers
    
    
def _download_geometries(place, download_method, tag,crs)

    if download_method == 'distance_from_address': 
        geometries_gdf = ox.geometries_from_address(place, tag = tag)
    elif download_method == 'OSMplace': 
        geometries_gdf = ox.geometries_from_place(place, tag = tag)
    else: 
        geometries_gdf = ox.geometries_from_polygon(place, tag = tag)
    
    geometries_gdf = geometries_gdf.to_crs(crs)
    return geometries_gdf
    
def railway_barriers(place, download_method,distance = None, epsg = None, keep_light_rail = False):
    """
    The function downloads overground railway structures from OSM. Such structures can be considered barriers which shape the Image of the City and obstruct sight and movement.
        
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data.
    distance: float
        it is used only if download_method == "distance from address"
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
    keep_light_rail: boolean
        considering light rail, like tramway
        
    Returns
    -------
    railway_barriers: LineString GeoDataFrame
        the railway barriers GeoDataFrame
    """    
    crs = {'EPSG:' + str(epsg)}
    tag = {"railway":"rail"}
    railways = _download_geometries(place, download_method, tag, crs)
    if "tunnel" in railways.columns:
        railways["tunnel"].fillna(0, inplace = True)
        railways = railways[railways["tunnel"] == 0]     
    r = railways.unary_union
    
    to_remove = 
    # removing light_rail, in case
    if not keep_light_rail:
        tag = {"railway":"light_rail"}
        light = _download_geometries(place, download_method, tag, crs)
        lr = light_railways.unary_union
        r = r.difference(lr)

    p = polygonize_full(r)
    railways = unary_union(p).buffer(10).boundary # to simpify a bit
    railways = _simplify_barrier(railways)
        
    df = pd.DataFrame({'geometry': features, 'type': ['railway'] * len(features)})
    railway_barriers = gpd.GeoDataFrame(df, geometry = df['geometry'], crs = crs)
    
    return railway_barriers
    
def park_barriers(place, download_method, distance = None, epsg = None, min_area = 100000):
    """
    The function downloads parks areas with a certain extent and converts them to LineString features. Parks may break continuity in the urban structure, besides being attractive areas for pedestrians.
        
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data.
    distance: float
        it is used only if download_method == "distance from address"
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
    min_area: double
        parks with an extension smaller that this parameter are disregarded
      
    Returns
    -------
    park_barriers: LineString GeoDataFrame
        the park barriers GeoDataFrame
    """

    crs = {'EPSG:' + str(epsg)}
    if download_method == 'distance_from_address':
        parks_polygon = ox.geometries_from_address(place, distance = distance, tags={"leisure": True})
    elif download_method == 'OSMplace': 
        parks_polygon = ox.geometries_from_place(place, tags={"leisure": True})
    else: 
        parks_polygon = ox.geometries_from_polygon(place, tags={"leisure": True})
    
    parks_polygon = parks_polygon[parks_polygon.leisure == 'park']
    ix_geo = parks_polygon.columns.get_loc("geometry")+1
    to_drop = []
    
    for row in parks_polygon.itertuples():
        type_geo = None
        try: 
            type_geo = row[ix_geo].geom_type
        except: 
            to_drop.append(row.Index)
        
    parks_polygon.drop(to_drop, axis = 0, inplace = True)
    parks_polygon = parks_polygon.to_crs(crs)
    parks_polygon.area = parks_polygon.geometry.area
    parks_polygon = parks_polygon[parks_polygon.area >= min_area]
 
    pp = parks_polygon['geometry'].unary_union  
    pp = polygonize_full(pp)
    parks = unary_union(pp).buffer(10).boundary # to simpify a bit

    if parks.type != "LineString": 
        parks = linemerge(parks)
        if parks.type != "LineString": 
            features = [i for i in parks]
        else: features = [parks]
    else: 
        features = [parks]

    df = pd.DataFrame({'geometry': features, 'type': ['park'] * len(features)})
    park_barriers = gpd.GeoDataFrame(df, geometry = df['geometry'], crs = crs)
    
    return park_barriers
    
   
def along_water(edges_gdf, barriers_gdf):
    """
    The function assigns to each street segment in a GeoDataFrame the list of barrierIDs corresponding to waterbodies which lay along the street segment. No obstructions between the street segment
    and the barriers are admitted.
        
    Parameters
    ----------
    edges_gdf: LineString GeoDataFrame
        the street segmentes GeoDataFrame 
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
        
    Returns
    -------
    edges_gdf: LineString GeoDataFrame
        the updated street segments GeoDataFrame
    """
    
    sindex = edges_gdf.sindex
    tmp = barriers_gdf[barriers_gdf['type'].isin(['water'])]
    edges_gdf['ac_rivers'] = edges_gdf.apply(lambda row: barriers_along(row['edgeID'], edges_gdf, tmp, sindex, offset = 200), axis = 1)
    edges_gdf['c_rivers'] = edges_gdf.apply(lambda row: _crossing_barriers(row['geometry'], tmp), axis = 1)
    edges_gdf['bridge'] = edges_gdf.apply(lambda row: True if len(row['c_rivers']) > 0 else False, axis = 1)
    # excluding bridges
    edges_gdf['a_rivers'] = edges_gdf.apply(lambda row: list(set(row['ac_rivers'])-set(row['c_rivers'])), axis = 1)
    edges_gdf['a_rivers'] = edges_gdf.apply(lambda row: row['ac_rivers'] if not row['bridge'] else [], axis = 1)
    edges_gdf.drop(['ac_rivers', 'c_rivers'], axis = 1, inplace = True)
    
    return edges_gdf

def along_within_parks(edges_gdf, barriers_gdf):
    """
    The function assigns to each street segment in a GeoDataFrame the list of barrierIDs corresponding to parks which lay along the street segment.
    Also street segments within parks are considered and the barriers are admitted.
        
    Parameters
    ----------
    edges_gdf: LineString GeoDataFrame
        the street segmentes GeoDataFrame 
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
        
    Returns
    -------
    edges_gdf: LineString GeoDataFrame
        the updated street segments GeoDataFrame
    """
    
    sindex = edges_gdf.sindex
    tmp = barriers_gdf[barriers_gdf['type']=='park']
    edges_gdf['a_parks'] = edges_gdf.apply(lambda row: barriers_along(row['edgeID'], edges_gdf, tmp, sindex, offset = 200), axis = 1)
    
    # polygonize parks
    park_polygons = barriers_gdf[barriers_gdf['type']=='park'].copy()
    park_polygons['geometry'] = park_polygons.apply(lambda row: (polygonize_full(row['geometry']))[0][0], axis = 1)
    park_polygons = gpd.GeoDataFrame(park_polygons['barrierID'], geometry = park_polygons['geometry'], crs = edges_gdf.crs)
    
    edges_gdf['w_parks'] = edges_gdf.apply(lambda row: _within_parks(row['geometry'], park_polygons), axis = 1) #within
    edges_gdf['aw_parks'] = edges_gdf.apply(lambda row: list(set(row['a_parks']+row['w_parks'])), axis = 1) #along
    edges_gdf.drop(['a_parks', 'w_parks'], axis = 1, inplace = True)

    return edges_gdf
    
def barriers_along(ix_line, edges_gdf, barriers_gdf, edges_gdf_sindex, offset = 100):
    """
    The function returns list of barrierIDs along the edgeID of a street segment, given a certain offset.
    Touching and intersecting barriers are ignored.
        
    Parameters
    ----------
    ix_line: int
        index street segment
    edges_gdf: LineString GeoDataFrame
        the street segmentes GeoDataFrame 
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
    edges_gdf_sindex: RTree Sindex
        spatial index on edges_gdf
    offset: int
        offset along the street segment considered
      
    Returns
    -------
    barriers_along: List
        a list of barriers along a given street segment
    """
    
    buffer = edges_gdf.loc[ix_line].geometry.buffer(offset)
    barriers_along = []
    intersecting_barriers = barriers_gdf[barriers_gdf.geometry.intersects(buffer)]
    touching_barriers = barriers_gdf[barriers_gdf.geometry.touches(edges_gdf.loc[ix_line].geometry)]
    intersecting_barriers = intersecting_barriers[~intersecting_barriers.barrierID.isin(list(touching_barriers.barrierID))]
    if len(intersecting_barriers) == 0: 
        return []
    
    possible_matches_index = list(edges_gdf_sindex.intersection(buffer.bounds))
    pm = edges_gdf.iloc[possible_matches_index]
    pm.drop(ix_line, axis = 0, inplace = True)
    
    for ix, barrier in intersecting_barriers.iterrows():
        midpoint = edges_gdf.loc[ix_line].geometry.interpolate(0.5, normalized = True)
        line = LineString([midpoint, nearest_points(midpoint, barrier['geometry'])[1]])
        if len(pm[pm.geometry.intersects(line)]) >= 1: 
            continue
        barriers_along.append(barrier['barrierID'])
    
    if len(barriers_along) == 0: 
        return []
    return barriers_along
    

    
def _within_parks(line_geometry, park_polygons):
    """
    The function supports the along_within_parks function. Returns a list containing the barrierID of possibly intersecting parks (should be one).
        
    Parameters
    ----------
    line_geometry: LineString 
        street segment geometry
    park_polygons: Polygon GeoDataFrame
        Parks GeoDataFrame
      
    Returns
    -------
    within: List
        a list of street segments within a given park's polygon
    """
    
    within = []
    intersecting_parks = park_polygons[park_polygons.geometry.intersects(line_geometry)]
    touching_parks = park_polygons[park_polygons.geometry.touches(line_geometry)]
    if len(intersecting_parks) == 0: 
        return within
    intersecting_parks = intersecting_parks[~intersecting_parks.barrierID.isin(list(touching_parks.barrierID))]
    within = list(intersecting_parks.barrierID)
    return within
    

def assign_structuring_barriers(edges_gdf, barriers_gdf):
    """
    The function return a GeoDataFrame with an added boolean column field that indicates whether the street segment intersects a separating/structuring barrier.
    
    Parameters
    ----------
    edges_gdf: LineString GeoDataFrame
        the street segmentes GeoDataFrame 
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
        
    Returns
    -------
    edges_gdf: LineString GeoDataFrame
        the updated street segments GeoDataFrame
    """
    
    barriers_gdf = barriers_gdf.copy()
    edges_gdf = edges_gdf.copy()
    tmp = barriers_gdf[barriers_gdf['type'] != 'park'].copy() # parks are disregarded
    
    edges_gdf['c_barr'] = edges_gdf.apply(lambda row: _crossing_barriers(row['geometry'], tmp ), axis = 1)
    edges_gdf['sep_barr'] = edges_gdf.apply(lambda row: True if len(row['c_barr']) > 0 else False, axis = 1)
    edges_gdf.drop('c_barr', axis = 1, inplace = True)
    
    return edges_gdf

def _crossing_barriers(line_geometry, barriers_gdf):
    """
    The function supports the assign_structuring_barriers and along_water functions. It returns a list of intersecting barrierIDs.
    
    Parameters
    ----------
    line_geometry: LineString 
        street segment geometry
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
        
    Returns
    -------
    adjacent_barriers: List
        a list of adjacent barriers to a given street segment
    """
    
    adjacent_barriers = []
    intersecting_barriers = barriers_gdf[barriers_gdf.geometry.intersects(line_geometry)]
    touching_barriers = barriers_gdf[barriers_gdf.geometry.touches(line_geometry)]
    if len(intersecting_barriers) == 0: 
        return adjacent_barriers
    intersecting_barriers = intersecting_barriers[~intersecting_barriers.barrierID.isin(list(touching_barriers.barrierID))]
    adjacent_barriers = list(intersecting_barriers.barrierID)
    return adjacent_barriers
    
def get_barriers(place, download_method, distance, epsg): 
    """
    The function returns all the barriers (water, park, railways, major roads) within a certain urban area.
    Certain parameter are set by default. For manipulating, use the barrier-type specific functions (see above).
    
    Parameters
    ----------
    place: string
        name of cities or areas in OSM: when using "OSMpolygon" please provide the name of a "relation" in OSM as an argument of "place"; when using "distance_from_address"
        provide an existing OSM address; when using "OSMplace" provide an OSM place name
    download_method: string, {"polygon", "distance_from_address", "OSMplace"}
        it indicates the method that should be used for downloading the data.
    distance: float
        it is used only if download_method == "distance from address"
    epsg: int
        epsg of the area considered; if None OSMNx is used for the projection
    keep_light_rail: boolean
        considering light rail, like tramway
        
    Returns
    -------
    barriers_gdf: LineString GeoDataFrame
        the barriers GeoDataFrame
    """
    
    rb = road_barriers(place, download_method, distance, epsg, include_primary = True)
    wb = water_barriers(place, download_method, distance, epsg)
    ryb = railway_barriers(place,download_method, distance, epsg)
    pb = park_barriers(place,download_method, distance, epsg, min_area = 100000)
    barriers_gdf = pd.concat([rb, wb, ryb, pb])
    barriers_gdf.reset_index(inplace = True, drop = True)
    barriers_gdf['barrierID'] = barriers_gdf.index.astype(int)

    return barriers_gdf
   
   
def _simplify_barrier(geometry)


    if geometry.type != "LineString":         
        geometry = linemerge(geometry)
        if geometry.type != "LineString": 
            features = [i for i in geometry]
        else: 
            features = [geometry]
    else: 
        features = [geometry]
        
    return features
        
def _create_gdf(geometries, crs)

    df = pd.DataFrame({'geometry': geometries})
    gdf = gpd.GeoDataFrame(df, geometry = df['geometry'], crs = crs)
    gdf['length'] = gdf['geometry'].length
    return gdf
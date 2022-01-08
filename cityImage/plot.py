import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as cols
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker

from mpl_toolkits.axes_grid1 import make_axes_locatable, ImageGrid
from mpl_toolkits.mplot3d.art3d import Line3DCollection
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import mapclassify

import pylab
import colorsys

pd.set_option("precision", 10)

from .utilities import scaling_columnDF
"""
Plotting functions

"""

## Plotting
    
class Plot():
    
    def __init__(self, fig_size, black_background, title):
    
        fig, ax = plt.subplots(1, figsize=(fig_size, fig_size))

        # background black or white - basic settings
        rect = fig.patch 
        if black_background: 
            text_color = "white"
            rect.set_facecolor("black")
        else: 
            text_color = "black"
            rect.set_facecolor("white")
        font_size = fig_size*2+5 # font-size
        fig.suptitle(title, color = text_color, fontsize=font_size, fontfamily = 'Times New Roman')
        fig.subplots_adjust(top=0.92)
        
        plt.axis("equal")
        self.fig, self.ax = fig, ax
        self.font_size, self.text_color = font_size, text_color
        
class MultiPlotGrid():
    
    def __init__(self, fig_size, nrows, ncols, black_background):
        
        figsize = (fig_size, fig_size*nrows)           
        fig = plt.figure(figsize=figsize)
        grid = ImageGrid(fig, 111, nrows_ncols=(nrows,ncols), axes_pad= (0.50, 1.00))
        rect = fig.patch 
        
        if black_background: 
            text_color = "white"
            rect.set_facecolor("black")
        else: 
            text_color = "black"
            rect.set_facecolor("white")
        
        font_size = fig_size+5 # font-size   
        self.fig, self.grid = fig, grid
        self.font_size, self.text_color = font_size, text_color
        
class MultiPlot():
    
    def __init__(self, fig_size, nrows, ncols, black_background, title = None):
    
        figsize = (fig_size, fig_size*nrows) 
        fig, grid = plt.subplots(nrows = nrows, ncols = ncols, figsize=figsize)

        rect = fig.patch 
        if black_background: 
            text_color = "white"
            rect.set_facecolor("black")
        else: 
            text_color = "black"
            rect.set_facecolor("white")
        
        font_size = fig_size+5
        if title is not None:
            fig.suptitle(title, color = text_color, fontsize = font_size, fontfamily = 'Times New Roman', 
                         ha = 'center', va = 'center') 
            fig.subplots_adjust(top=0.92)
         
        self.fig, self.grid = fig, grid
        self.font_size, self.text_color = font_size, text_color

def _single_plot(ax, gdf, column = None, scheme = None, bins = None, classes = None, norm = None, cmap = None, color = None, alpha = None, 
                legend = False, ms = None, ms_factor = None, lw = None, lw_factor = None,  zorder = 0):
    """
    It plots the geometries of a GeoDataFrame, coloring on the bases of the values contained in column, using a given scheme, on the provided Axes.
    If only "column" is provided, a categorical map is depicted.
    If no column is provided, a plain map is shown.
    
    Parameters
    ----------
    ax: matplotlib.axes object
        the Axes on which plotting
    gdf: GeoDataFrame
        GeoDataFrame to be plotted 
    column: string
        Column on which the plot is based
    scheme: string
        classification method, choose amongst: https://pysal.org/mapclassify/api.html
    bins: list
        bins defined by the user
    classes: int
        classes for visualising when scheme is not "None"
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    color: string
        categorical color applied to all geometries when not using a column to color them
    alpha: float
        alpha value of the plotted layer
    legend: boolean
        if True, show legend, otherwise don't
    ms: float
        point size value, when plotting a Point GeoDataFrame
    ms_factor: float 
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the ms_factor to rescale the marker size accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a Point GeoDataFrame
    lw: float
        line width, when plotting a LineString GeoDataFrame
    lw_factor: float
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the lw_factor to rescale the line width accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a LineString GeoDataFrame
    zorder: int   
        zorder of this layer; e.g. if 0, plots first, thus main GeoDataFrame on top; if 1, plots last, thus on top.
    """  
    
    gdf = gdf.copy()
    categorical = True
    if alpha is None:
        alpha = 1
    if column is not None: 
        gdf = gdf.reindex(gdf[column].abs().sort_values(ascending = True).index)
    
    # single-colour map
    if (column is None) & (scheme is None) & (color is None):
        color = 'red'
    
    # categorical map
    elif (column is not None) & (scheme is None) & (norm is None) & (cmap is None): 
        cmap = rand_cmap(len(gdf[column].unique()))         
    
    # Lynch's bins - only for variables from 0 to 1 
    elif scheme == "Lynch_Breaks":  
        scaling_columnDF(gdf, column)
        column = column+"_sc"
        bins = [0.125, 0.25, 0.5, 0.75, 1.00]
        scheme = 'User_Defined'
        categorical = False
    
    elif norm is not None:
        legend = False
        categorical = False
        scheme = None
    
    elif (scheme is not None) & (classes is None) & (bins is None):
        classes = 7   
    
    if (scheme is not None) & (cmap is None) :
        cmap = kindlmann()
    
    if (scheme is not None) | (norm is not None):
        categorical = False
        color = None
    
    if (column is not None) & (not categorical):
        if (gdf[column].dtype == 'O'):
            gdf[column] = gdf[column].astype(float)
    
    if bins is None: 
        c_k = {None}
        if classes is not None:
            c_k = {"k" : classes}
    else: 
        c_k = {'bins':bins, "k" : len(bins)}
        scheme = 'User_Defined'
    
    if gdf.iloc[0].geometry.geom_type == 'Point':
        if (ms_factor is not None): 
            # rescale
            scaling_columnDF(gdf, column)
            gdf['ms'] = np.where(gdf[column+'_sc'] >= 0.20, gdf[column+'_sc']*ms_factor, 0.40) # marker size
            ms = gdf['ms']
        elif ms is None:
            ms = 1.0
        else: 
            ms = ms

        gdf.plot(ax = ax, column = column, markersize = ms, categorical = categorical, color = color, scheme = scheme, cmap = cmap, norm = norm, alpha = alpha,
            legend = legend, classification_kwds = c_k, zorder = zorder) 
        
    if gdf.iloc[0].geometry.geom_type == 'LineString':
        if (lw is None) & (lw_factor is None): 
            lw = 1.00
        elif lw_factor is not None:
            lw = [(abs(value)*lw_factor) if (abs(value)*lw_factor) > 1.1 else 1.1 for value in gdf[column]]
        
        gdf.plot(ax = ax, column = column, categorical = categorical, color = color, linewidth = lw, scheme = scheme, alpha = alpha, cmap = cmap, norm = norm,
            legend = legend, classification_kwds = c_k, capstyle = 'round', joinstyle = 'round', zorder = zorder) 
                
    if gdf.iloc[0].geometry.geom_type == 'Polygon': 
        gdf.plot(ax = ax, column = column, categorical = categorical, color = color, scheme = scheme, edgecolor = 'none', alpha = alpha, cmap = cmap,
            norm = norm, legend = legend, classification_kwds = c_k, zorder = zorder) 
        
 
def plot_gdf(gdf, column = None, title = None, black_background = True, fig_size = 15, scheme = None, bins = None, classes = None, norm = None, cmap = None, color = None, alpha = None, 
                legend = False, cbar = False, cbar_ticks = 5, cbar_max_symbol = False, only_min_max = False, axes_frame = False, ms = None, ms_factor = None, lw = None, lw_factor = None, gdf_base_map = pd.DataFrame({"a" : []}), base_map_color = None, base_map_alpha = 0.4,
                base_map_lw = 1.1, base_map_ms = 2.0, base_map_zorder = 0):
    """
    It plots the geometries of a GeoDataFrame, coloring on the bases of the values contained in column, using a given scheme.
    If only "column" is provided, a categorical map is depicted.
    If no column is provided, a plain map is shown.
    
    Parameters
    ----------
    gdf: GeoDataFrame
        GeoDataFrame to be plotted 
    column: string
        Column on which the plot is based
    title: string 
        title of the plot
    black_background: boolean 
        black background or white
    fig_size: float
        size of the figure's side extent
    scheme: string
        classification method, choose amongst: https://pysal.org/mapclassify/api.html
    bins: list
        bins defined by the user
    classes: int
        number of classes for categorising the data when scheme is not "None"
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    color: string
        categorical color applied to all geometries when not using a column to color them
    alpha: float
        alpha value of the plotted layer
    legend: boolean
        if True, show legend, otherwise don't
    cbar: boolean
        if True, show colorbar, otherwise don't; when True it doesn't show legend
    cbar_ticks: int
        number of ticks along the colorbar
    cbar_max_symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    axes_frame: boolean
        if True, it shows the axes' frame
    ms: float
        point size value, when plotting a Point GeoDataFrame
    ms_factor: float 
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the ms_factor to rescale the marker size accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a Point GeoDataFrame
    lw: float
        line width, when plotting a LineString GeoDataFrame
    lw_factor: float
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the lw_factor to rescale the line width accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a LineString GeoDataFrame
    gdf_base_map: GeoDataFrame
        a desired additional layer to use as a base map        
    base_map_color: string
        color applied to all geometries of the base map
    base_map_alpha: float
        base map's alpha value
    base_map_ms: float
        base map's marker size when the base map is a Point GeoDataFrame
    base_map_lw: float
        base map's line width when the base map is a LineString GeoDataFrame
    base_map_zorder: int   
        zorder of the layer; e.g. if 0, plots first, thus main GeoDataFrame on top; if 1, plots last, thus on top.
        
    Returns
    -------
    fig: matplotlib.figure.Figure object
        the resulting figure
    """   
    
    # fig,ax set up
    plot = Plot(fig_size = fig_size, black_background = black_background, title = title)
    fig, ax = plot.fig, plot.ax
    
    ax.set_aspect("equal")
    if axes_frame: 
        _set_axes_frame(ax, black_background, plot.text_color)
    else: 
        ax.set_axis_off()     
    
    zorder = 0
    # base map (e.g. street network)
    if (not gdf_base_map.empty):
        if gdf_base_map.iloc[0].geometry.geom_type == 'LineString':
            gdf_base_map.plot(ax = ax, color = base_map_color, linewidth = base_map_lw, alpha = base_map_alpha, zorder = base_map_zorder)
        if gdf_base_map.iloc[0].geometry.geom_type == 'Point':
            gdf_base_map.plot(ax = ax, color = base_map_color, markersize = base_map_ms, alpha = base_map_alpha, zorder = base_map_zorder)
        if gdf_base_map.iloc[0].geometry.geom_type == 'Polygon':
            gdf_base_map.plot(ax = ax, color = base_map_color, alpha = base_map_alpha, zorder = base_map_zorder)
        if base_map_zorder == 0:
            zorder = 1
   
    _single_plot(ax, gdf, column = column, scheme = scheme, bins = bins, classes = classes, norm = norm, cmap = cmap, color = color, alpha = alpha, 
                ms = ms, ms_factor = ms_factor, lw = lw, lw_factor = lw_factor, zorder = zorder, legend = legend)

    if legend: 
        _generate_legend_ax(ax, plot.font_size-5, black_background) 
        
    if (cbar) & (not legend):
        if norm is None:
            min_value = gdf[column].min()
            max_value = gdf[column].max()
            norm = plt.Normalize(vmin = min_value, vmax = max_value)
            
        generate_row_colorbar(cmap, fig, ax, ncols = 1, text_color = plot.text_color, font_size = plot.font_size, norm = norm, 
                             ticks = cbar_ticks,symbol = cbar_max_symbol, only_min_max = only_min_max)
    
    return fig    
                
def plot_barriers(barriers_gdf, lw = 1.1, title = "Plot", legend = False, axes_frame = False, black_background = True,                 
               fig_size = 15, gdf_base_map = pd.DataFrame({"a" : []}), base_map_color = None, base_map_alpha = 0.4,
               base_map_lw = 1.1, base_map_ms = 2.0, base_map_zorder = 0):
    """
    It creates a plot from a lineString GeoDataFrame. 
    When column and scheme are not "None" it plots the distribution over value and geographical space of variable "column using scheme
    "scheme". If only "column" is provided, a categorical map is depicted.
    
    It plots the distribution over value and geographical space of variable "column" using "scheme". 
    If only "column" is provided, a categorical map is depicted.
    Otherwise, a plain map is shown.
    
    Parameters
    ----------
    barriers_gdf: GeoDataFrame
    
    lw: float
        line width
    title: str 
        title of the graph
    legend: boolean
        if True, show legend, otherwise don't
    axes_frame: boolean
        if True, it shows the axes' frame 
    black_background: boolean 
        black background or white
    fig_size: float
        size of the figure's side extent
    gdf_base_map: GeoDataFrame
        a desired additional layer to use as a base map        
    base_map_color: string
        color applied to all geometries of the base map
    base_map_alpha: float
        base map's alpha value
    base_map_ms: float
        base map's marker size when the base map is a Point GeoDataFrame
    base_map_lw: float
        base map's line width when the base map is a LineString GeoDataFrame
    base_map_zorder: int   
        zorder of the layer; e.g. if 0, plots first, thus main GeoDataFrame on top; if 1, plots last, thus on top.
        
    Returns
    -------
    fig: matplotlib.figure.Figure object
        the resulting figure
    """   
    barriers_gdf = barriers_gdf.copy()    
    
    # fig,ax set up
    plot = Plot(fig_size = fig_size, black_background = black_background, title = title)
    fig, ax = plot.fig, plot.ax
    
    ax.set_aspect("equal")
    if axes_frame: 
        _set_axes_frame(ax, black_background, plot.text_color)
    else: 
        ax.set_axis_off()     
    
    zorder = 0
    # background (e.g. street network)
    if (not gdf_base_map.empty):
        if gdf_base_map.iloc[0].geometry.geom_type == 'LineString':
            gdf_base_map.plot(ax = ax, color = base_map_color, linewidth = base_map_lw, alpha = base_map_alpha,zorder = base_map_zorder)
        if gdf_base_map.iloc[0].geometry.geom_type == 'Point':
            gdf_base_map.plot(ax = ax, color = base_map_color, markersize = base_map_ms, alpha = base_map_alpha, zorder = base_map_zorder)
        if gdf_base_map.iloc[0].geometry.geom_type == 'Polygon':
            gdf_base_map.plot(ax = ax, color = base_map_color, alpha = base_map_alpha, zorder = base_map_zorder)
        if base_map_zorder == 0:
            zorder = 1
    
    barriers_gdf['barrier_type'] = barriers_gdf['type']
    barriers_gdf.sort_values(by = 'barrier_type', ascending = False, inplace = True)  
    
    colors = ['green', 'red', 'gray', 'blue']
    if 'secondary_road' in list(barriers_gdf['type'].unique()):
        colors[3] = 'darkgray'
        colors.append('blue')
        
    colormap = LinearSegmentedColormap.from_list('new_map', colors, N=len(colors))
    barriers_gdf.plot(ax = ax, categorical = True, column = 'barrier_type', cmap = colormap, linewidth = lw, legend = legend, 
                     label =  'barrier_type', zorder = zorder )             
                     
    if legend: 
        _generate_legend_ax(ax, plot.font_size-10, black_background)
    
    return fig
    
def plot_gdfs(list_gdfs = [], column = None, ncols = 2, main_title = None, titles = [], black_background = True, fig_size = 15, scheme = None, bins = None, classes = None, norm = None, cmap = None, color = None, alpha = None, 
                legend = False, cbar = False, cbar_ticks = 5, cbar_max_symbol = False, only_min_max = False, axes_frame = False, ms = None, ms_factor = None, lw = None, lw_factor = None): 
                     
    """
    It plots the geometries of a list of GeoDataFrame, containing the same type of geometry. Coloring is based on a provided column (that needs to be a column in each passed GeoDataFrame), using a given scheme.
    If only "column" is provided, a categorical map is depicted.
    If no column is provided, a plain map is shown.
    
    Parameters
    ----------
    list_gdfs: list of GeoDataFrames
        GeoDataFrames to be plotted
    column: string
        Column on which the plot is based
    main_title: string 
        main title of the plot
    titles: list of string
        list of titles to be assigned to each quadrant (axes) of the grid
    black_background: boolean 
        black background or white
    fig_size: float
        size figure extent
    scheme: string
        classification method, choose amongst: https://pysal.org/mapclassify/api.html
    bins: list
        bins defined by the user
    classes: int
        number of classes for categorising the data when scheme is not "None"
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    color: string
        categorical color applied to all geometries when not using a column to color them
    alpha: float
        alpha value of the plotted layer
    legend: boolean
        if True, show legend, otherwise don't
    cbar: boolean
        if True, show colorbar, otherwise don't; when True it doesn't show legend
    cbar_ticks: int
        number of ticks along the colorbar
    cbar_max_symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    axes_frame: boolean
        if True, it shows the axes' frame
    ms: float
        point size value, when plotting a Point GeoDataFrame
    ms_factor: float 
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the ms_factor to rescale the marker size accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a Point GeoDataFrame
    lw: float
        line width, when plotting a LineString GeoDataFrame
    lw_factor: float
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the lw_factor to rescale the line width accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a LineString GeoDataFrame   
        
    
    Returns
    -------
    fig: matplotlib.figure.Figure object
        the resulting figure
    """              
                     
    if ncols == 2:
        nrows, ncols = int(len(list_gdfs)/2), 2
        if (len(list_gdfs)%2 != 0): 
            nrows = nrows+1
    else:
        nrows, ncols = int(len(list_gdfs)/3), 3
        if (len(list_gdfs)%3 != 0): 
            nrows = nrows+1

    multiPlot = MultiPlot(fig_size = fig_size, nrows = nrows, ncols = ncols, black_background = black_background, 
                          title = main_title)
    
    fig, grid = multiPlot.fig, multiPlot.grid   
    legend_fig = False
    
    if nrows > 1: 
        grid = [item for sublist in grid for item in sublist]
    for n, ax in enumerate(grid):
                
        ax.set_aspect("equal")
        if axes_frame: 
            _set_axes_frame(ax, black_background, multiPlot.text_color)
        else: 
            ax.set_axis_off()      

        if n > len(list_gdfs)-1: 
            continue # when odd nr of gdfs    
        
        gdf = list_gdfs[n]
        if len(titles) > 0:
            ax.set_title(titles[n], loc='center', fontfamily = 'Times New Roman', fontsize = multiPlot.font_size, color = multiPlot.text_color,  pad = 15)
            
        if (n == ncols*nrows/2) & legend & ((scheme == 'User_Defined') | (scheme == 'Lynch_Breaks')):
            legend_ax = True
            legend_fig = True
        elif legend & ((scheme != 'User_Defined') & (scheme != 'Lynch_Breaks')):
            legend_ax = True
        else: 
            legend_ax = False
            legend_fig = False
        
        _single_plot(ax, gdf, column = column, scheme = scheme, bins = bins, classes = classes, norm = norm, cmap = cmap, color = color, alpha = alpha, legend = legend_ax, 
                    ms = ms, ms_factor = ms_factor, lw = lw, lw_factor = lw_factor)
                    
        if legend_fig:
            _generate_legend_fig(ax, nrows, multiPlot.text_color, (multiPlot.font_size-5), black_background)
        elif legend_ax:
            _generate_legend_ax(ax, (multiPlot.font_size-15), black_background)
    
    if (cbar) & (not legend):
        if norm is None:
            min_value = min([gdf[column].min() for gdf in list_gdfs])
            max_value = max([gdf[column].max() for gdf in list_gdfs])
            norm = plt.Normalize(vmin = min_value, vmax = max_value)
        generate_grid_colorbar(cmap, fig, grid, nrows, ncols, multiPlot.text_color,(multiPlot.font_size-5), norm = norm, ticks = cbar_ticks, 
                              symbol = cbar_max_symbol, only_min_max = only_min_max )
            
    return fig
   
def plot_gdf_grid(gdf = None, columns = [], ncols = 2, titles = [], black_background = True, fig_size = 15, scheme = None, bins = None, classes = None, norm = None, cmap = None, color = None, alpha = None, 
                legend = False, cbar = False, cbar_ticks = 5, cbar_max_symbol = False, only_min_max = False, axes_frame = False, ms = None, ms_factor = None, lw = None, lw_factor = None): 
    """
    It plots the geometries of a GeoDataFrame, coloring on the bases of the values contained in the provided columns, using a given scheme.
    If only "column" is provided, a categorical map is depicted.
    If no column is provided, a plain map is shown.
    
    Parameters
    ----------
    gdf: GeoDataFrame
        GeoDataFrame to be plotted 
    column: string
        Column on which the plot is based
    title: string 
        title of the plot
    black_background: boolean 
        black background or white
    fig_size: float
        size figure extent
    scheme: string
        classification method, choose amongst: https://pysal.org/mapclassify/api.html
    bins: list
        bins defined by the user
    classes: int
        number of classes for categorising the data when scheme is not "None"
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    color: string
        categorical color applied to all geometries when not using a column to color them
    alpha: float
        alpha value of the plotted layer
    legend: boolean
        if True, show legend, otherwise don't
    cbar: boolean
        if True, show colorbar, otherwise don't; when True it doesn't show legend
    cbar_ticks: int
        number of ticks along the colorbar
    cbar_max_symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    axes_frame: boolean
        if True, it shows the axes' frame
    ms: float
        point size value, when plotting a Point GeoDataFrame
    ms_factor: float 
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the ms_factor to rescale the marker size accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a Point GeoDataFrame
    lw: float
        line width, when plotting a LineString GeoDataFrame
    lw_factor: float
        when provided, it rescales the column provided, if any, from 0 to 1 and it uses the lw_factor to rescale the line width accordingly 
        (e.g. rescaled variable's value [0-1] * factor), when plotting a LineString GeoDataFrame
    """   
    
    if ncols == 2:
        nrows, ncols = int(len(columns)/2), 2
        if (len(columns)%2 != 0): 
            nrows = nrows+1
    else:
        nrows, ncols = int(len(columns)/3), 3
        if (len(columns)%3 != 0): 
            nrows = nrows+1
     
    multiPlot = MultiPlotGrid(fig_size = fig_size, nrows = nrows, ncols = ncols, black_background = black_background)
    fig, grid = multiPlot.fig, multiPlot.grid   
    legend_fig = False
    
    for n, ax in enumerate(grid):
        
        ax.set_aspect("equal")
        if axes_frame: 
            _set_axes_frame(ax, black_background, multiPlot.text_color)
        else: 
            ax.set_axis_off()
        
        if n > len(columns)-1: 
            continue # when odd nr of columns
        
        column = columns[n]
        if len(titles) > 0:          
            ax.set_title(titles[n], loc='center', fontfamily = 'Times New Roman', fontsize = multiPlot.font_size, color = multiPlot.text_color,  pad = 15)
        
        if (n == ncols*nrows/2) & legend & ((scheme == 'User_Defined') | (scheme == 'Lynch_Breaks')):
            legend_ax = True
            legend_fig = True
        elif legend & ((scheme != 'User_Defined') & (scheme != 'Lynch_Breaks')):
            legend_ax = True
        else: 
            legend_ax = False
            legend_fig = False
        
        _single_plot(ax, gdf, column = column, scheme = scheme, bins = bins, classes = classes, norm = norm, cmap = cmap, color = color, alpha = alpha, legend = legend_ax,
                    ms = ms, ms_factor = ms_factor, lw = lw, lw_factor = lw_factor)
                            
        if legend_fig:
            _generate_legend_fig(ax, nrows, multiPlot.text_color, multiPlot.font_size-5, black_background)
        elif legend_ax:
            _generate_legend_ax(ax, (multiPlot.font_size-5), black_background)

    if (cbar) & (not legend):
        if norm is None:
            min_value = min([gdf[column].min() for column in columns])
            max_value = max([gdf[column].max() for column in columns])
            norm = plt.Normalize(vmin = min_value, vmax = max_value)
        generate_grid_colorbar(cmap, fig, grid, nrows, ncols, multiPlot.text_color,multiPlot.font_size-5, norm = norm, ticks = cbar_ticks, 
                              symbol = cbar_max_symbol, only_min_max = only_min_max)

    return fig
    
def plot_multiplex(M, multiplex_edges):
    node_Xs = [float(node["x"]) for node in M.nodes.values()]
    node_Ys = [float(node["y"]) for node in M.nodes.values()]
    node_Zs = np.array([float(node["z"])*2000 for node in M.nodes.values()])
    node_size = []
    size = 1
    node_color = []

    for i, d in M.nodes(data=True):
        if d["station"]:
            node_size.append(9)
            node_color.append("#ec1a30")
        elif d["z"] == 1:
            node_size.append(0.0)
            node_color.append("#ffffcc")
        elif d["z"] == 0:
            node_size.append(8)
            node_color.append("#ff8566")

    lines = []
    line_width = []
    lwidth = 0.4
    
    # edges
    for u, v, data in M.edges(data=True):
        xs, ys = data["geometry"].xy
        zs = [M.node[u]["z"]*2000 for i in range(len(xs))]
        if data["layer"] == "intra_layer": 
            zs = [0, 2000]
        
        lines.append([list(a) for a in zip(xs, ys, zs)])
        if data["layer"] == "intra_layer": 
            line_width.append(0.2)
        elif data["pedestrian"] == 1: 
            line_width.append(0.1)
        else: 
            line_width.append(lwidth)

    fig_height = 40
    lc = Line3DCollection(lines, linewidths=line_width, alpha=1, color="#ffffff", zorder=1)

    west, south, east, north = multiplex_edges.total_bounds
    bbox_aspect_ratio = (north - south) / (east - west)*1.5
    fig_width = fig_height +90 / bbox_aspect_ratio/1.5
    fig = plt.figure(figsize=(15, 15))
    ax = fig.gca(projection="3d")
    ax.add_collection3d(lc)
    ax.scatter(node_Xs, node_Ys, node_Zs, s=node_size, c=node_color, zorder=2)
    ax.set_ylim(south, north)
    ax.set_xlim(west, east)
    ax.set_zlim(0, 2500)
    ax.axis("off")
    ax.margins(0)
    ax.tick_params(which="both", direction="in")
    fig.canvas.draw()
    ax.set_facecolor("black")
    ax.set_aspect("equal")

    return(fig)
    
def _generate_legend_fig(ax, nrows, ncols, text_color, font_size, black_background):
    """ 
    It generates the legend for an entire figure.
    
    Parameters
    ----------
    ax: matplotlib.axes object
        the Axes on which plotting
    nrows: int
        number of rows in the figure
    text_color: string
        the text color
    font_size: int
        the legend's labels text size
    """
    
    leg = ax.get_legend() 
    plt.setp(leg.texts, family='Times New Roman', fontsize = font_size, color = text_color, va = 'center')
    
    if ncols == 2:
        if nrows%2 == 0: 
            leg.set_bbox_to_anchor((2.15, 1.00, 0.33, 0.33))    
        else: 
            leg.set_bbox_to_anchor((1.15, 0.5, 0.33, 0.33))
    
    elif ncols == 3:
        if nrows%2 == 0: 
            leg.set_bbox_to_anchor((2.25, 1.15, 0.33, 0.33))    
        else:     
            leg.set_bbox_to_anchor((1.25, 0.65, 0.33, 0.33))
        
    leg.get_frame().set_linewidth(0.0) # remove legend border
    leg.set_zorder(102)
    leg.get_frame().set_facecolor('none')
    
    for handle in leg.legendHandles:
        handle._legmarker.set_markersize(15)

def _generate_legend_ax(ax, font_size, black_background):
    """ 
    It generate the legend for a figure.
    
    Parameters
    ----------
    ax: matplotlib.axes object
        the Axes on which plotting
    text_color: string
        the text color
    font_size: int
        the legend's labels text size
    """
    leg = ax.get_legend()  
    if black_background:
        text_color = 'black'
    else: 
        text_color = 'white'
    
    plt.setp(leg.texts, family='Times New Roman', fontsize = font_size, color = text_color, va = 'center')
    leg.set_bbox_to_anchor((0., 0., 0.2, 0.2))
    leg.get_frame().set_linewidth(0.0) # remove legend border
    leg.set_zorder(102)
    
    for handle in leg.legendHandles:
        handle._legmarker.set_markersize(12)
    if not black_background:
        leg.get_frame().set_facecolor('black')
        leg.get_frame().set_alpha(0.90)  
    else:
        leg.get_frame().set_facecolor('white')
        leg.get_frame().set_alpha(0.90)  
 
def generate_grid_colorbar(cmap, fig, grid, nrows, ncols, text_color, font_size, norm = None, ticks = 5, symbol = False, only_min_max = False):
    """ 
    It generates a colorbar for an entire grid of axes.
    
    Parameters
    ----------
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    fig: matplotlib.figure.Figure
        The figure container for the current plot
    grid: array of Axes, mpl_toolkits.axes_grid1.axes_grid.ImageGrid
        the list of Axes or the ImageGrid object
    nrows: int
        the number of "rows" in the grid/figure
    ncols: int
        the number of "columns" in the grid/figure
    text_color: string
        the text color    
    font_size: int
        the colorbar's labels text size
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    ticks: int
        the number of ticks along the colorbar
    symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    """
    
    if font_size is None: 
        font_size = 20
    
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm._A = []
    vr_p = 1/30.30
    hr_p = 0.5/30.30
    ax = grid[0]
 
    if ncols == 2:
        width = ax.get_position().x1*ncols-hr_p-ax.get_position().x0
    else:
        width = ax.get_position().x1*(ncols-1)+0.10

    if nrows == 1: 
        pos = [ax.get_position().x0+width, ax.get_position().y0, 0.027, ax.get_position().height]
    elif nrows%2 == 0:
        y0 = (ax.get_position().y0-(ax.get_position().height*(nrows-1))-vr_p)+(nrows/2-0.5)*ax.get_position().height
        pos = [ax.get_position().x0+width, y0, 0.027, ax.get_position().height]
    else:
        ax = grid[nrows-1]
        pos = [ax.get_position().x0+width, ax.get_position().y0, 0.027, ax.get_position().height]

    _set_colorbar(fig, pos, sm, norm, text_color, font_size, ticks, symbol, only_min_max)    
    
def generate_row_colorbar(cmap, fig, ax, ncols, text_color, font_size, norm = None, ticks = 5, symbol = False, only_min_max = False):
    """ 
    It generates a colorbar for a specific row of a figure.
    
    Parameters
    ----------
    cmap: string, matplotlib.colors.LinearSegmentedColormap
        see matplotlib colormaps for a list of possible values or pass a colormap
    fig: matplotlib.figure.Figure
        The figure container for the current plot    
    ax: matplotlib.axes object
        the Axes on which plotting
    ncols: int
        the number of "columns" in the grid/figure
    text_color: string
        the text color
    font_size: int
        the colorbar's labels text size
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    ticks: int
        the number of ticks along the colorbar
    symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    """
    
    if font_size is None: 
        font_size = 20
    
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm._A = []
    vr_p = 1/30.30
    hr_p = 0.5/30.30
    
    width = ax.get_position().x1
    if ncols == 2:
        width = ax.get_position().x1*ncols-hr_p-ax.get_position().x0
    elif ncols > 2:
        width = ax.get_position().x1*(ncols-1)-hr_p*ncols
    pos = [ax.get_position().x0+width, ax.get_position().y0, 0.05, ax.get_position().height]
    
    _set_colorbar(fig, pos, sm, norm, text_color, font_size, ticks, symbol, only_min_max)    
    
    
def _set_colorbar(fig, pos, sm, norm, text_color, font_size, ticks, symbol, only_min_max = False):
    """ 
    It plots a colorbar, given some settings.
    
    Parameters
    ----------
    fig: matplotlib.figure.Figure
        The figure container for the current plot
    pos: list of float
        the axes positions
    sm: matplotlib.cm.ScalarMappable
        a mixin class to map scalar data to RGBA
    norm: array
        a class that specifies a desired data normalisation into a [min, max] interval
    text_color: string
        the text color
    font_size: int
        the colorbar's labels text size
    ticks: int
        the number of ticks along the colorbar
    symbol: boolean
        if True, it shows the ">" next to the highest tick's label in the colorbar (useful when normalising)
    only_min_max: boolean
        if True, it only shows the ">" and "<" as labels of the lowest and highest ticks' the colorbar
    """

    cax = fig.add_axes(pos, frameon = False)
    cax.tick_params(size=0)
    cb = plt.colorbar(sm, cax=cax)
    cb.outline.set_visible(False)
    tick_locator = ticker.MaxNLocator(nbins=ticks)
    cb.locator = tick_locator
    cb.update_ticks()
    cb.outline.set_visible(False)
    
    ticks = list(cax.get_yticks())
    for t in ticks: 
        if (t == ticks[-1]) & (t != norm.vmax) :
            ticks[-1] = norm.vmax

    if only_min_max:
        ticks = [norm.vmin, norm.vmax]
    cb.set_ticks(ticks)
    
    if symbol:
        cax.set_yticklabels([round(t,1) if t < norm.vmax else "> "+str(round(t,1)) for t in cax.get_yticks()])
    else: 
        cax.set_yticklabels([round(t,1) for t in cax.get_yticks()])
    
    plt.setp(plt.getp(cax.axes, "yticklabels"), color = text_color, fontfamily = 'Times New Roman', fontsize=font_size)
             
def normalize(n, range1, range2):
    """ 
    It generate the legend for a figure.
    
    Parameters
    ----------
    ax:
    
    nrows:
    
    text_color:
    
    font_size:
    
    black_background:
    
    Returns
    -------
    cmap:  matplotlib.colors.Colormap
        the color map
    """  
    delta1 = range1[1] - range1[0]
    delta2 = range2[1] - range2[0]
    return (delta2 * (n - range1[0]) / delta1) + range2[0]           

def random_colors_list_hsv(nlabels, vmin = 0.8, vmax = 1.0):
    """ 
    It generates a list of random HSV colors, given the number of classes, min and max values in the HSV spectrum.
    
    Parameters
    ----------
    nlabels: int
        the number of categories to be coloured 
    type_color: string {"soft", "bright"} 
        it defines whether using bright or soft pastel colors, by limiting the RGB spectrum
       
    Returns
    -------
    cmap: matplotlib.colors.LinearSegmentedColormap
        the color map
    """
    randHSVcolors = [(np.random.uniform(low=0.0, high=0.95),
                      np.random.uniform(low=0.4, high=0.95),
                      np.random.uniform(low= vmin, high= vmax)) for i in range(nlabels)]

    return  randHSVcolors

def random_colors_list_rgb(nlabels, vmin = 0.8, vmax = 1.0):
    """ 
    It generates a categorical random color map, given the number of classes
    
    Parameters
    ----------
    nlabels: int
        the number of categories to be coloured 
    type_color: string {"soft", "bright"} 
        it defines whether using bright or soft pastel colors, by limiting the RGB spectrum
       
    Returns
    -------
    cmap: matplotlib.colors.LinearSegmentedColormap
        the color map
    """ 
    
    randHSVcolors = [(np.random.uniform(low=0.0, high=0.95),
                      np.random.uniform(low=0.4, high=0.95),
                      np.random.uniform(low= vmin, high= vmax)) for i in range(nlabels)]

    # Convert HSV list to RGB
    randRGBcolors = []
    for HSVcolor in randHSVcolors: 
        randRGBcolors.append(colorsys.hsv_to_rgb(HSVcolor[0], HSVcolor[1], HSVcolor[2]))
    return  randRGBcolors
    
            
# Generate random colormap
def rand_cmap(nlabels, type_color ='soft'):
    """ 
    It generates a categorical random color map, given the number of classes
    
    Parameters
    ----------
    nlabels: int
        the number of categories to be coloured 
    type_color: string {"soft", "bright"} 
        it defines whether using bright or soft pastel colors, by limiting the RGB spectrum
       
    Returns
    -------
    cmap: matplotlib.colors.LinearSegmentedColormap
        the color map
    """   
    if type_color not in ('bright', 'soft'):
        type_color = 'bright'
    
    # Generate color map for bright colors, based on hsv
    if type_color == 'bright':
        randHSVcolors = [(np.random.uniform(low=0.0, high=0.8),
                          np.random.uniform(low=0.2, high=0.8),
                          np.random.uniform(low=0.9, high=1.0)) for i in range(nlabels)]

        # Convert HSV list to RGB
        randRGBcolors = []
        for HSVcolor in randHSVcolors:
            randRGBcolors.append(colorsys.hsv_to_rgb(HSVcolor[0], HSVcolor[1], HSVcolor[2]))


        random_colormap = LinearSegmentedColormap.from_list('new_map', randRGBcolors, N=nlabels)

    # Generate soft pastel colors, by limiting the RGB spectrum
    if type_color == 'soft':
        low = 0.6
        high = 0.95
        randRGBcolors = [(np.random.uniform(low=low, high=high),
                          np.random.uniform(low=low, high=high),
                          np.random.uniform(low=low, high=high)) for i in range(nlabels)]

        random_colormap = LinearSegmentedColormap.from_list('new_map', randRGBcolors, N=nlabels)

    return random_colormap

def kindlmann():
    """ 
    It returns a Kindlmann color map. See https://ieeexplore.ieee.org/document/1183788
       
    Returns
    -------
    cmap: matplotlib.colors.LinearSegmentedColormap
        the color map
    """   

    kindlmann_list = [(0.00, 0.00, 0.00,1), (0.248, 0.0271, 0.569, 1), (0.0311, 0.258, 0.646,1),
            (0.019, 0.415, 0.415,1), (0.025, 0.538, 0.269,1), (0.0315, 0.658, 0.103,1),
            (0.331, 0.761, 0.036,1),(0.768, 0.809, 0.039,1), (0.989, 0.862, 0.772,1),
            (1.0, 1.0, 1.0)]
    cmap = LinearSegmentedColormap.from_list('kindlmann', kindlmann_list)
    return cmap
    
def _set_axes_frame(ax, black_background, text_color):
    """ 
    It draws the axis frame.
    
    Parameters
    ----------
    ax: matplotlib.axes
        the Axes on which plotting
    black_background: boolean
        it indicates if the background color is black
    text_color: string
        the text color
    """
    ax.xaxis.set_ticklabels([])
    ax.yaxis.set_ticklabels([])
    ax.tick_params(axis= 'both', which= 'both', length=0)
    
    for spine in ax.spines:
        ax.spines[spine].set_color(text_color)
    if black_background: 
        ax.set_facecolor('black')
      
def cmap_from_colors(list_colors):
    """ 
    It generates a colormap given a list of colors.
    
    Parameters
    ----------
    list_colors: list of string
        the list of colours
       
    Returns
    -------
    cmap:  matplotlib.colors.LinearSegmentedColormap
        the color map
    """   
    cmap = LinearSegmentedColormap.from_list('custom_cmap', list_colors)
    return cmap
    
def lighten_color(color, amount=0.5):
    """
    Lightens the given color by multiplying (1-luminosity) by the given amount.
    Input can be matplotlib color string, hex string, or RGB tuple.

    Examples:
    >> lighten_color('g', 0.3)
    >> lighten_color('#F034A3', 0.6)
    >> lighten_color((.3,.55,.1), 0.5)
    """
    import matplotlib.colors as mc
    import colorsys
    try:
        c = mc.cnames[color]
    except:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])
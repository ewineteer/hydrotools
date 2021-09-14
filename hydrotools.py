import rasterio as rio
from rasterio.mask import mask
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from tqdm import tqdm


# Identify the downstream watershed for each watershed in a shapefile.
def route(polyws_path, faccpath, fdirpath, routedpath=None):

    # This function uses the flow direction at the outlet of the watershed to 
    # determine where it should look for the downstream watershed. This dictionary
    # maps the flow direction integers to coordinates where it should look for 
    # the downstream watershed. Remember, NOT ALL FDIR RASTERS USE THIS COORDINATE
    # SYSTEM. You may need to edit this dictionary for some fdir rasters. It's the
    # most common though.
    dirdict = {1:[1,0],
               2:[1,-1],
               4:[0,-1],
               8:[-1,-1],
               16:[-1,0],
               32:[-1,1],
               64:[0,1],
               128:[1,1]
              }

    # The watershed shapefile needs to have a column labeled 'wsid'
    watersheds = gpd.read_file(polyws_path)
    # Creating a spatial index of the watershed to improve search speed. This 
    # won't help with smaller basins, but for big areas it's useful.
    ws_sindex = watersheds.sindex


    # Creating downstream watershed column
    watersheds['dsid'] = np.nan
    watersheds['wsid'] = watersheds.wsid.astype('int')

    # Iterate through each watershed
    for i, watershedrow in tqdm(watersheds.iterrows()):


        dsid = None
        # Create list containing current watershed's geometry
        watershed = [watershedrow.geometry]


        # Read flow accumulation for watershed area
        with rio.open(faccpath) as src:
            faccras, facctrans = mask(src, watershed, crop=True, indexes=1)
            srctrans = src.transform

            pixelSizeX = srctrans[0]
            pixelSizeY =-srctrans[4]

            srccrs = src.crs
            faccmeta = src.meta

        # Getting coordinates of maximum facc    
        xmax,ymax = np.where(faccras==np.max(faccras))
        xcoord,ycoord = rio.transform.xy(facctrans, xmax, ymax)
        
        # Turn coordinates into shapely geometry
        maxfacgeo = [Point(xcoord,ycoord)]
        
        # Open fdir raster at that coordinate
        with rio.open(fdirpath) as src:
            fdirras, facctrans = mask(src, maxfacgeo, crop=True, indexes=1)

        # Get flow direction and corresponding downstream coordinates
        dirkey = fdirras[0,0]
        xmult,ymult = dirdict[dirkey]
        
        # Calculate coordinates of downstream watershed
        dsxcoord = [xcoord + pixelSizeX*xmult]
        dsycoord = [ycoord + pixelSizeY*ymult]
        
        # Convert to shapely geometry
        dsgeo = [Point(dsxcoord[0],dsycoord[0])]
        
        # Get approximate matches for downstream watersheds
        nearby_ws_inds = list(ws_sindex.intersection(watershed[0].bounds))
        
        # Get approximate matches into geodataframe
        nearby_ws = watersheds.loc[nearby_ws_inds,:]
        
        # Find precise match for downstream watershed
        for j,row in nearby_ws.iterrows():
            if dsgeo[0].within(row.geometry):
                dsid = row.wsid
                break
        
        # If there's no match, that means it's an outlet watershed
        if pd.isna(dsid):
            watersheds.loc[i,'dsid'] = -1
        else:
            watersheds.loc[i,'dsid'] = dsid

    if routedpath:
        watersheds.to_file(routedpath)
    else:
        return(watersheds)
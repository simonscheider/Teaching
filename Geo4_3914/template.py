#-------------------------------------------------------------------------------
# Name:        Geo4_3914 template
# Purpose:     This template can be used to load and analyse urban infrastructure data from OSM. It is meant for the course
#               Methods and Techniques Specialisation
#               BASIC GIS WITH PYTHON AND WEB RESOURCES
#               at the department for Human Geography and Planning , Utrecht university
#               This script has methods that are left empty. They need to be filled in by you during the course

#
# Author:      Simon Scheider
#
# Created:     13/02/2018
# Copyright:   (c) simon 2018
# Licence:     CC BY
#-------------------------------------------------------------------------------

#These are the Python modules (libraries that need to be installed)
import overpy
import arcpy
import os
import numpy

#--------------
class OSMLoad():
  ''' For getting and storing OSM data as .shp (for a given key value pair/element type)'''

  idlist = [] #List of OSM identifiers in the result set
  key = '' #This the OSM place category key
  value = '' #This the OSM place category value
  elem = "" #The OSM geometry type (node, line, area)
  tag_set = set()# this is the list of tags that come with the result set
  max_field_length = 0
  result = '' #This the result object



  """Turns an OSM element (from a result set) into an arcpy point geometry, depending on OSM element type and a target reference system (rs)"""
  def createGeometry(self, element, rs):
    if (self.elem == "node"):
         geom = arcpy.PointGeometry(arcpy.Point(float(element.lon), float(element.lat)),arcpy.SpatialReference(4326)).projectAs(rs)
    elif (self.elem == "way"):
        try:
            geom = arcpy.PointGeometry(arcpy.Point(float(element.center.lon), float(element.center.lat)),arcpy.SpatialReference(4326)).projectAs(rs)
        except AttributeError:
            array = arcpy.Array()
            for n in element.get_nodes(resolve_missing=True):
                array.add(arcpy.Point(float(n.lon), float(n.lat)))
            geom = arcpy.PointGeometry(arcpy.Polygon(array,arcpy.SpatialReference(4326)).projectAs(rs).centroid) #gets the centroid
    return geom

  """Turns the loaded OSM results into a point shape file located at "outFC", depending on a target reference system (rs)"""
  def toShape(self, outFC, rs):
         # Create the output feature class in WGS84
        #outFC = os.path.join(arcpy.env.workspace,arcpy.ValidateTableName("OSM"))
        if self.elem == "node":
            fc = 'POINT'
            res = self.result.nodes
        elif self.elem == "way":
            fc = 'POINT'
            res = self.result.ways
##        elif self.elem == "line":
##            fc = 'POLYLINE'
##            res = self.result.ways
        #This genereates the output feature class
        arcpy.CreateFeatureclass_management(os.path.dirname(outFC), os.path.basename(outFC), fc, '', '', '', rs)

        # Join fields to the feature class, using ExtendTable, depending on the OSM tags that came with the loaded results
        tag_list = (list(self.tag_set))
        print tag_list
        ff = (lambda s: (str(arcpy.ValidateFieldName((s[0:4])+(s[-5:]) if len(s) >= 10 else s))).upper())
        #This makes sure the tag names are converted into valid fieldnames (of length 10 max), where the first and the last 5 characters are taken to build the string
        tag_fields = map(ff, tag_list)

        print tag_fields

        field_array = [('intfield', numpy.int32),
                        ('Name_d', '|S255'),
                        ('Value_d', '|S255'),
                        ('Key_d', '|S255'),
                        ]
        for f in tag_fields:
            field_array.append((f, '|S255'))

        #print field_array
        inarray = numpy.array([],
                          numpy.dtype(field_array))
        #print field_array
        arcpy.da.ExtendTable(outFC, "OID@", inarray, "intfield")


        field_list = ['Name_d', 'Value_d', 'Key_d', 'SHAPE@']
        field_list.extend(tag_fields)
        #print field_list
        rowsDA = arcpy.da.InsertCursor(outFC, field_list)

        #Geometries and attributes are inserted
        for element in res:
            geom = self.createGeometry(element, rs)
            f = lambda tag: element.tags.get(tag, "n/a")
            tag_values = map(f,tag_list)
            #print tag_values
            l = [element.tags.get("name", "n/a"), element.tags.get(self.key, "n/a"), self.key, geom]
            l.extend(tag_values)
            try:
              rowsDA.insertRow(l)
            except RuntimeError, e:
              arcpy.AddError(str(e))
        if rowsDA:
            del rowsDA

  """Gets data from OSM using the overpass API. Input is some Overpass expression consisting of an OSm element, a key value pair and some Bounding box. It stores reslts internally into self object"""
  def getOSM(self, overpassexpr):

        #Extracts the syntax elements of the overpass expression (element, key and value)
        print 'get OSM data for: '  + overpassexpr
        a = ['(','['] #Find the first bracketted expression to get the element name
        OSMelem =  overpassexpr[0:min(overpassexpr.find(i) for i in a)].strip()
        kv = ((overpassexpr.split('[')[1]).split(']')[0]).strip()
        key = (kv.split('=')[0]).strip()
        value = (kv.split('=')[1]).strip()
        api = overpy.Overpass()
        #Using Overpass API: http://wiki.openstreetmap.org/wiki/Overpass_API
        result = api.query(overpassexpr)

        results = []
        if (OSMelem == "node"):
            results = result.nodes
        elif (OSMelem == "way"):
            results = result.ways
        else:
            raise ValueError("OSM element missing (Syntax) for getting data!!")

        print("Number of results:" + str(len(results)))
        self.max_field_length = 0

        for element in results:
            self.idlist.append(element.id)
            #print node.tags
            # print node.tags.
            #print element.id
            for tag in element.tags:
                #print(tag+": %s" % element.tags.get(tag, "n/a"))
                self.tag_set.add(tag)
                self.max_field_length= max(len(element.tags.get(tag, "n/a")),self.max_field_length)

        self.result = result
        self.elem = OSMelem
        self.value = value
        self.key = key
#------------end of load object-------------------------



###Here we start the methods that should be coded by you.  The lines commented like this need to be substituted with Python arcpy code

"""This method has a municipality name as input, selects the mun. object in a municipality layer, and stores the single municipality into a shapefile"""
def getMunicipality(gemname, filen=r"C:\Temp\MTGIS\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM"):
    print ("Getting data for "+gemname)
    out = os.path.join(arcpy.env.workspace, gemname+'.shp')
    arcpy.MakeFeatureLayer_management(filen, 'municipalities_l')
    arcpy.SelectLayerByAttribute_management('municipalities_l', where_clause=fieldname+"= '"+gemname+"' ")
    arcpy.CopyFeatures_management('municipalities_l', out)
    return out

"""This method has a (municipality) shapefile as input, then gets its reference system (rs), gets the first geometry's extent, reprojects it to WGS 84, and returns a bbox, the rs and the extent"""
def getBBfromFile(filen):
    print ("Getting BB")
    ##This needs to be filled in by you. You need to generate an extent (ext) object and an rs object
    ##
    ##
    ##
    bbox = ", ".join(str(e) for e in [ext.YMin,ext.XMin,ext.YMax,ext.XMax])
    return (bbox, rs, ext)

"""This method has a bbox, an OSM element and a key and a value as input and returns an overpass expression"""
def constructOverpassEx(bbox, OSMelem = "node", keyvalue = {'key':"amenity", 'value' : 'school'}):
    overpassexpr = ''

    #bbox = ", ".join(str(e) for e in BBcoordinates) "50.600, 7.100, 50.748, 7.157"
    if (keyvalue["value"] == None): #If querying only by key
            kv = keyvalue["key"]
    else:
            kv = keyvalue["key"]+"="+keyvalue["value"]

    ## Here you need to generate the overpass expression out of its elements
    return overpassexpr

"""This method generates a distance raster from a shapefile"""
def distanceRaster(shapefile):
    print ("Generate distance raster")
    out = os.path.join(arcpy.env.workspace, 'distrast')
    ##Here you need to be generate a raster file at the location where "out" is
    return out

"""This method generates a point density raster from a shapefile"""
def densityRaster(shapefile):
    print ("Generate density raster")
    out = os.path.join(arcpy.env.workspace, 'densrast')
    ## Here you need to generate a raster file at the location where "out" is
    return out

"""This method generates a shapefile of city neighborhoods that are within a municipality"""
def getCityNeighborhoods(buurtfile= "wijkenbuurten2017/buurt_2017", within = 'Utrecht.shp'):
    print ("Get city neighorhoods for "+within)
    out = os.path.join(arcpy.env.workspace, 'buurten.shp')
    ## Here you need to generate a shapefile at the location of "out" which contains the neighborhoods within the given municipality ("within")
    ##
    ##
    return out

"""This method aggregates a raster into a neighborhood shapefile using a Zonal mean, and stores it as a table"""
def aggRasterinNeighborhoods(raster, buurt = "buurten.shp"):
    print ("Aggregate "+raster +" into "+buurt)
    out = os.path.join(arcpy.env.workspace, os.path.splitext(os.path.basename(raster))[0]+'b.dbf')
    ## Here you need to generate a zonal means table over the input raster within the input neighborhoods, and save it as "out"
    return out




"""This is the predefined procedure that this script is supposed to carry out. Each line is a processing step, however some cannot be acarried out yet.
The result are 2 city neighborhood files (tables) that can be mapped and which show the mean density/distance within each neighborhood."""
def main():

    #0) Setting computing environment
    arcpy.env.overwriteOutput = True #Such that files can be overwritten
    arcpy.env.workspace = r"C:\Temp\MTGIS" #Setting the workspace
    if arcpy.CheckExtension("Spatial") == "Available": #Check out spatial analyst extension
        arcpy.CheckOutExtension("Spatial")

    #1) Getting city municipality file for city outline (bounding box), and setting the processing extent
    municipality = getMunicipality("Utrecht", filen=r"C:\Temp\MTGIS\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM")
    b = getBBfromFile(municipality)
    bb = b[0] #Getting the bounding box (string) in WGS 84
    rs = b[1] #Getting the reference system of the original municipality file
    ext = b[2] #Getting the extent object in the original reference system
    arcpy.env.extent = ext  #Setting the geoprocessing extent to the municipality outline in the original reference system

    #2) Loading data for the municipality from OSM and save it
    o = OSMLoad() #Create object for loading OSM data
    exp = constructOverpassEx(bb,OSMelem = "node", keyvalue = {'key':"amenity", 'value' : 'school'}) #Generate overpass expression from bounding box
    o.getOSM(exp) #Getting data from OSM
    tname = os.path.join(arcpy.env.workspace,r"result.shp") #Filename for storing results
    o.toShape(tname, rs) #Store results

    #3) Compute analytic rasters and aggregate them into neighborhoods within municipality
    distraster = distanceRaster(tname) #generating distance raster
    densraster = densityRaster(tname) #generating density raster
    buurt = getCityNeighborhoods(buurtfile= "wijkenbuurten2017/buurt_2017.shp", within = municipality)
    densbuurt = aggRasterinNeighborhoods(densraster,buurt) #aggregate means into neighborhoods
    distbuurt = aggRasterinNeighborhoods(distraster,buurt)


if __name__ == '__main__':
    main()

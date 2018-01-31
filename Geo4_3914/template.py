#-------------------------------------------------------------------------------
# Name:        Geo4_3914 template
# Purpose:      This template can be used to load and analyse urban infrastructure data from OSM.
#
# Author:      Simon Scheider
#
# Created:     29/01/2018
# Copyright:   (c) simon 2018
# Licence:     <your licence>
#-------------------------------------------------------------------------------

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



  """Turns an OSM element (from a result set) into an arcpy geometry, depending on loaded geometry type and a target reference system (rs)"""
  def createGeometry(self, element, rs):
    if (self.elem == "node"):
         geom = arcpy.PointGeometry(arcpy.Point(float(element.lon), float(element.lat)),arcpy.SpatialReference(4326)).projectAs(rs)
    elif (self.elem == "area"):
         array = arcpy.Array()
         for n in element.get_nodes(resolve_missing=True):
            array.add(arcpy.Point(float(n.lon), float(n.lat)))
         geom = arcpy.Polygon(array,arcpy.SpatialReference(4326)).projectAs(rs)
    elif (self.elem == "line"):
         array = arcpy.Array()
         for n in element.get_nodes(resolve_missing=True):
            array.add(arcpy.Point(float(n.lon), float(n.lat)))
         geom = arcpy.Polyline(array,arcpy.SpatialReference(4326)).projectAs(rs)
    return geom

  """Turns the loaded OSM results into a shape file located at "outFC", depending on the loaded geometry type (element) and a target reference system (rs)"""
  def toShape(self, outFC, rs):
         # Create the output feature class in WGS84
        #outFC = os.path.join(arcpy.env.workspace,arcpy.ValidateTableName("OSM"))
        if self.elem == "node":
            fc = 'POINT'
            res = self.result.nodes
        elif self.elem == "area":
            fc = 'POLYGON'
            res = self.result.ways
        elif self.elem == "line":
            fc = 'POLYLINE'
            res = self.result.ways
        #This genereates the output feature class
        arcpy.CreateFeatureclass_management(os.path.dirname(outFC), os.path.basename(outFC), fc, '', '', '', rs)

        # Join fields to the feature class, using ExtendTable, depending on the OSM tags that came with the loaded results
        tag_list = (list(self.tag_set))
        print tag_list
        #This makes sure the tag names are converted into valid fieldnames (of length 10 max)
        tag_fields = map(lambda s: (((str(arcpy.ValidateFieldName(s))))[0:4]+((str(arcpy.ValidateFieldName(s))))[-5:] if len(str(arcpy.ValidateFieldName(s)))>10 else (str(arcpy.ValidateFieldName(s)))).upper(), tag_list)
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


  def getOSM(self, overpassexpr):

        #Extracts the syntax elements of the overpass expression (element, key and value)
        print 'get OSM data for: '  + overpassexpr
        OSMelem =  (overpassexpr.split('(')[0]).strip()
        kv = ((overpassexpr.split('[')[1]).split(']')[0]).strip()
        key = (kv.split('=')[0]).strip()
        value = (kv.split('=')[1]).strip()
        api = overpy.Overpass()
        #Using Overpass API: http://wiki.openstreetmap.org/wiki/Overpass_API
        result = api.query(overpassexpr)


        results = []
        if (OSMelem == "node"):
            results = result.nodes
        elif (OSMelem == "area" or OSMelem == "line"):
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
#------------end of load object------------------------



def constructOverpassEx(bbox, OSMelem = "node", keyvalue = {'key':"amenity", 'value' : 'school'}):
    overpassexpr = ''

    #bbox = ", ".join(str(e) for e in BBcoordinates) "50.600, 7.100, 50.748, 7.157"
    if (keyvalue["value"] == None): #If querying only by key
            kv = keyvalue["key"]
    else:
            kv = keyvalue["key"]+"="+keyvalue["value"]

    overpassexpr = OSMelem+"""("""+bbox+""") ["""+kv+"""];out body;  """
    return overpassexpr


    # Gets the extent of the current map view in WGS84   and the original reference system
def getBBinWGS84():
        cmapdoc = arcpy.mapping.MapDocument("CURRENT")
        cdf = arcpy.mapping.ListDataFrames(cmapdoc, "Layers")[0]
        extentPolygon = arcpy.Polygon(arcpy.Array([cdf.extent.lowerLeft,cdf.extent.lowerRight, cdf.extent.upperRight, cdf.extent.upperLeft]), cdf.spatialReference)
        rs = cdf.spatialReference
        extentPolygoninWGS84 = extentPolygon.projectAs("WGS 1984") #arcpy.SpatialReference(4326)
        ex = extentPolygoninWGS84.extent
        bbox = ", ".join(str(e) for e in [ex.YMin,ex.XMin,ex.YMax,ex.XMax])
        return (bbox, rs)
        del cmapdoc
    #print getCurentBBinWGS84()


def main():
    tname = r"C:\Temp\result.shp"
    b = getCurrentBBinWGS84()
    bb = b[0]
    rs = b[1]
    o = OSMLoad()
    o.getOSM(constructOverpassEx(bb))
    o.toShape(tname, rs)

if __name__ == '__main__':
    main()

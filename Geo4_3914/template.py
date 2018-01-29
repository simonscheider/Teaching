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


class OSMLoad():
  ''' For getting and storing OSM data as .shp (for a given key value pair/element type)'''

  idlist = [] #List of OSM identifiers in the result set
  key = '' #This the OSM place category key
  value = '' #This the OSM place category value
  elem = "" #The OSM geometry type (node, line, area)
  tag_set = set()# this is the list of tags that come with the result set
  max_field_length = 0
  result = '' #This the result object
  rs = '' #This the reference system object of the current mapview



    # Gets the extent of the current map view in WGS84
  def getCurrentBBinWGS84(self):
        cmapdoc = arcpy.mapping.MapDocument("CURRENT")
        cdf = arcpy.mapping.ListDataFrames(cmapdoc, "Layers")[0]
        extentPolygon = arcpy.Polygon(arcpy.Array([cdf.extent.lowerLeft,cdf.extent.lowerRight, cdf.extent.upperRight, cdf.extent.upperLeft]), cdf.spatialReference)
        self.rs = cdf.spatialReference
        extentPolygoninWGS84 = extentPolygon.projectAs("WGS 1984") #arcpy.SpatialReference(4326)
        ex = extentPolygoninWGS84.extent
        return [ex.YMin,ex.XMin,ex.YMax,ex.XMax]
        del cmapdoc
    #print getCurentBBinWGS84()


  """Turns an OSM element (from a result set) into an arcpy geometry"""
  def createGeometry(self, element):
    if (self.elem == "node"):
         geom = arcpy.PointGeometry(arcpy.Point(float(element.lon), float(element.lat)),arcpy.SpatialReference(4326)).projectAs(self.rs)
    elif (self.elem == "area"):
         array = arcpy.Array()
         for n in element.get_nodes(resolve_missing=True):
            array.add(arcpy.Point(float(n.lon), float(n.lat)))
         geom = arcpy.Polygon(array,arcpy.SpatialReference(4326)).projectAs(self.rs)
    elif (self.elem == "line"):
         array = arcpy.Array()
         for n in element.get_nodes(resolve_missing=True):
            array.add(arcpy.Point(float(n.lon), float(n.lat)))
         geom = arcpy.Polyline(array,arcpy.SpatialReference(4326)).projectAs(self.rs)
    return geom

  """Turns the loaded OSM results into a shape file at "outFC", depending on geometry type"""
  def OSMtoShape(self, outFC):
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

        arcpy.CreateFeatureclass_management(os.path.dirname(outFC), os.path.basename(outFC), fc, '', '', '', self.rs)

        # Join fields to the feature class, using ExtendTable


        tag_list = (list(self.tag_set))
        print tag_list
        tag_fields = map(lambda s: (((str(arcpy.ValidateFieldName(s))))[0:4]+((str(arcpy.ValidateFieldName(s))))[-5:] if len(str(arcpy.ValidateFieldName(s)))>10 else (str(arcpy.ValidateFieldName(s)))).upper(), tag_list)
        print tag_fields

        field_array = [('intfield', numpy.int32),
                        ('Name_d', '|S255'),
                        ('Value_d', '|S255'),
                        ('Key_d', '|S255'),
                        ]
        for f in tag_fields:
            field_array.append((f, '|S255'))

##        for f in field_array:
##            arcpy.AddField_management(outFC,f[0], f[1])
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
            geom = self.createGeometry(element)
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


  def getOSMfeatures(self, OSMelem = "node", keyvalue = {'key':"amenity", 'value' : 'school'}):
        api = overpy.Overpass()

        bbox = ", ".join(str(e) for e in self.getCurrentBBinWGS84())#"50.600, 7.100, 50.748, 7.157"

        if (keyvalue["value"] == None): #If querying only by key
            kv = keyvalue["key"]
        else:
            kv = keyvalue["key"]+"="+keyvalue["value"]

        #Using Overpass API: http://wiki.openstreetmap.org/wiki/Overpass_API
        result = api.query(OSMelem+"""("""+bbox+""") ["""+kv+"""];out body;
            """)
        results = []
        if (OSMelem == "node"):
            results = result.nodes
        elif (OSMelem == "area" or OSMelem == "line"):
            results = result.ways

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
        self.value = keyvalue["value"]
        self.key = keyvalue["key"]


def main():
    tname = r"C:\Temp\result.shp"
    o = OSMLoad()
    o.getOSMfeatures()
    o.OSMtoShape(tname)

if __name__ == '__main__':
    main()

#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      Schei008
#
# Created:     21/02/2018
# Copyright:   (c) Schei008 2018
# Licence:     <your licence>
#-------------------------------------------------------------------------------




import arcpy
import numpy
import numbers
import os
import json, requests
import nltk
import string
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from nltk.stem.snowball import DutchStemmer
from nltk import wordpunct_tokenize
import placewebscraper

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import CountVectorizer

#This is the LDA Python library for topic modeling
import lda


def tryKeys(o, k1):
    try:
        out = o[k1]
        return out
    except Exception, e:
        print 'key error:'+str(e)
        return e

def getFSPlaces(city = 'Utrecht, NL', section='food', limit=50):
    url = 'https://api.foursquare.com/v2/venues/explore'
    out =[]
    outfile=os.path.join(arcpy.env.workspace, city+section+'fsdata.json')
    with open(outfile, 'w') as fp:
        params = dict(
          client_id='VD5JRI5HLXSD21ZJUALG0K4BJOAVJNBIUXUNJDSDHERAYSA0',
          client_secret='J3SNUNCWZ4NCJU1YLP211M4K5ATSBEYRT12VFPNXC4RMYQ5Z',
          near = city,
          section = section,
          #query = 'mexican',
          v = '20170801' ,
          limit=limit
        )
        resp = requests.get(url=url, params=params)
        data = json.loads(resp.text)
        recommendedvenues = (data['response']['groups'][0])['items']
        print data['response']['totalResults']
        for v in recommendedvenues:
            p = {}
            print ''
            place = tryKeys(v['venue'],'name')
            p['Name']  = place
            print 'Place: '+ place
            url =  tryKeys(v['venue'],'url')
            if not isinstance(url, Exception):
                print 'URL: '+ url
                p['url']  =url
                wt = placewebscraper.scrape(url)
                if wt !=None:
                    print 'webtext: '+wt['text']
                    p['webtext']=  wt['text']
            rate = tryKeys(v['venue'],'rating')
            if not isinstance(url, Exception):
                print 'Rating: '+  str(rate)
                p['rating'] = str(rate)
            lat = str(tryKeys(v['venue']['location'],'lat'))
            lon = str(tryKeys(v['venue']['location'],'lng'))
            print 'Location: '+ lat+' ' +lon
            p['lat'] = lat
            p['lon']  = lon
            add = tryKeys(v['venue']['location'],'formattedAddress')
            if not isinstance(add, Exception):
                print 'Address: '+ ', '.join(add)
                p['address'] = ', '.join(add)
            cat = tryKeys(v['venue'],'categories')
            if not isinstance(cat, Exception):
                print 'Categories: '+', '.join([c['name'] for c in cat])
                p['cat']   = ', '.join([c['name'] for c in cat])
            menu = tryKeys(v['venue'],'menu')
            if  not isinstance(menu, Exception):
                menuurl = tryKeys(menu,'url')
                if not isinstance(menuurl, Exception):
                        print 'Menu: '+ str(menuurl)
                        p['menuurl'] = menuurl
                        wt = placewebscraper.scrape(menuurl)
                        if wt !=None:
                            p['menutext'] =  wt['text']
            tips = tryKeys(v, 'tips')
            if not isinstance(tips, Exception):
                texts = [t['text'] for t in tips]
                tt = {}
                for t in texts:
                    l = findLanguage(t)
                    if  l in tt.keys():
                        tt[l]= tt[l]+ '; ' +t
                    else:
                        tt[l]= t
                #print 'Tips: '+'| '.join([text+' ('+findLanguage(text)+ ')' for text in texts])
                p['tips']  = tt
            out.append(p)
            fp.seek(0)
            json.dump(out, fp)
    fp.close()
    return outfile

def findLanguage(text):
    languages_ratios = {}
    tokens = wordpunct_tokenize(text)
    words = [word.lower() for word in tokens]
    for language in stopwords.fileids():
        stopwords_set = set(stopwords.words(language))
        words_set = set(words)
        common_elements = words_set.intersection(stopwords_set)

        languages_ratios[language] = len(common_elements) # language "score"
        languages_ratios
    return max(languages_ratios, key=languages_ratios.get)

def createGeometry(element, rs):
    geom = arcpy.PointGeometry(arcpy.Point(float(element['lon']), float(element['lat'])),arcpy.SpatialReference(4326)).projectAs(rs)
    return geom

def normalizeFieldList(keylist):
        print keylist
        ff = (lambda s: (str(arcpy.ValidateFieldName((s[0:4])+(s[-5:]) if len(s) >= 10 else s))).upper())
        #This makes sure the tag names are converted into valid fieldnames (of length 10 max), where the first and the last 5 characters are taken to build the string
        tag_fields = map(ff, keylist)
        print tag_fields
        return tag_fields


def json2SHP(dictionary, outFC, keylist, rs):
     #This genereates the output feature class
        arcpy.CreateFeatureclass_management(os.path.dirname(outFC), os.path.basename(outFC), 'POINT', '', '', '', rs)

        # Join fields to the feature class, using ExtendTable, depending on the OSM tags that came with the loaded results

        tag_fields = normalizeFieldList(keylist)

        #Find out data type of attributes by the first row
        obj = next(iter(dictionary))
        f = lambda tag: isinstance(obj.get(tag, 'nan'),numbers.Real) #Tests whether value is a float or not
        types = map(f,keylist)

        field_array = [('intfield', numpy.int32),
                        ('Name_d', '|S255')
                        ]
        for idx,f in enumerate(tag_fields):
            if types[idx]:
                field_array.append((f, numpy.float32))
            else:
                field_array.append((f, '|S255'))

        #print field_array
        inarray = numpy.array([],
                          numpy.dtype(field_array))
        #print field_array
        arcpy.da.ExtendTable(outFC, "OID@", inarray, "intfield")


        field_list = ['Name_d', 'SHAPE@']
        field_list.extend(tag_fields)
        #print field_list
        rowsDA = arcpy.da.InsertCursor(outFC, field_list)

        #Geometries and attributes are inserted
        for obj in dictionary:
            geom = createGeometry(obj, rs)
            f = lambda tag: (obj.get(tag, None))
            #[f(tag) for idx,tag in enumerate(keylist) if types(idx)]
            tag_values = map(f,keylist)
            #print tag_values
            l = [obj.get("Name", "n/a"), geom]
            l.extend(tag_values)
            try:
              rowsDA.insertRow(l)
            except RuntimeError, e:
              arcpy.AddError(str(e))
        if rowsDA:
            del rowsDA

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
    rs = arcpy.Describe(filen).spatialReference
    sc = arcpy.da.SearchCursor(filen, ["SHAPE@"])
    geom = sc.next()[0]
    ext = geom.extent.projectAs("WGS 1984")
    bbox = ", ".join(str(e) for e in [ext.YMin,ext.XMin,ext.YMax,ext.XMax])
    return (bbox, rs, ext)


def loadJson(jsonfile):
     with open(jsonfile) as data:
        return json.load(data)

def writeJson(dictionary, outfile):
     with open(outfile, 'w') as fp:
        fp.seek(0)
        json.dump(dictionary, fp)
        fp.close()

def addJSON(jsonfile,diclist, outjson, ids = None):
    diclistorigin = loadJson(jsonfile)
    newdiclist = []
    for idx, dicnew in  enumerate(diclist):
        if ids == None:
            dic = diclistorigin[idx].copy()
        else:
            dic = diclistorigin[ids[idx]].copy()
        dic.update(dicnew)
        newdiclist.append(dic)

    writeJson(newdiclist,outjson)

def joinJSON(jsonfile1, jsonfile2,outfile):
    j1 = loadJson(jsonfile1)
    j2 = loadJson(jsonfile2)
    writeJson(j1 + j2,outfile)
    return outfile





def tokenize(text, language = 'dutch'):
    """ Method turns a text into tokens removing stopwords and stemming them."""
    if language == 'dutch':
        p_stemmer = DutchStemmer()
    else:
        p_stemmer = PorterStemmer()

    text = text.lower()
    stop = set(stopwords.words(language))
    tokens = nltk.word_tokenize(text)
    tokens = [i for i in tokens if i not in string.punctuation and len(i)>=3]
    tokens = [i for i in tokens if i not in stop]
    tokens = [i for i in tokens if i.isalpha()]
    tokens = [p_stemmer.stem(i) for i in tokens]
    return tokens


def getTexts(jsonfile, key):
    d = loadJson(jsonfile)
    texts = []
    ids = []
    for idx,dic in enumerate(d):
         text = tryKeys(dic, key)
         if not isinstance(text,Exception):
            texts.append(dic[key])
            ids.append(idx)
    return texts, ids

def getTopics(texts, titles,language = 'dutch'):
    #This is where the texts get turned into a document-term matrix
    vectorizer = CountVectorizer(min_df = 1, stop_words = stopwords.words(language), analyzer = 'word', tokenizer=tokenize)
    X = vectorizer.fit_transform(texts)
    #print(X)
    #Gets the vocabulary of stemmed words (terms)
    vocab = vectorizer.get_feature_names()
    print(vocab)
    #This computes the LDA model
    model = lda.LDA(n_topics=18, n_iter=600, random_state=300)
    model.fit(X)
    topic_word = model.topic_word_
    #print("type(topic_word): {}".format(type(topic_word)))
    print("shape: {}".format(topic_word.shape))

    # get the top 5 words for each topic (by probablity)
    n = 5
    c = 0
    for i, topic_dist in enumerate(topic_word):
        topic_words = numpy.array(vocab)[numpy.argsort(topic_dist)][:-(n+1):-1]
        print('*Topic {}\n- {}'.format(i, ' '.join(topic_words)))
        c += 1
    #return model
    # apply topic model to new test data set and write topics into feature vector
    doc_topic_test = model.transform(X)
    #print(doc_topic_test)
    i = 0
    result = []
    for title, topics in zip(titles, doc_topic_test):
        title =str(title).encode('utf-8')
        print("{} (top topic: {})".format(title, topics.argmax()))
        f = {}
        for j,t in enumerate(topics):
                f['topic '+str(j)]= t
        result.append(f)
        i+=1
    return result

"""This method generates a kernel density raster from a point shapefile"""
def kdensityRaster(shapefile, mun, populationfield):
    print ("Generate kernel density raster")
    out = os.path.join(arcpy.env.workspace, mun+'kdr'+populationfield)
    outKDens = arcpy.sa.KernelDensity(shapefile, populationfield, 50, 500,"SQUARE_KILOMETERS")
    outKDens.save(out)
    return out

"""This method generates a point density raster from a shapefile"""
def densityRaster(shapefile, mun, populationfield):
    print ("Generate density raster")
    out = os.path.join(arcpy.env.workspace, mun+'dr'+populationfield)
    outDens = arcpy.sa.PointDensity(shapefile, populationfield, "50", arcpy.sa.NbrCircle(500, "MAP"), "SQUARE_KILOMETERS")
    outDens.save(out)
    return out


    """This method has a (municipality) shapefile as input, then gets its reference system (rs), gets the first geometry's extent, reprojects it to WGS 84, and returns a bbox, the rs and the extent"""
def getExtentfromFile(filen):
    print ("Getting BB")
    ext = arcpy.Describe(filen).extent
    bbox = ", ".join(str(e) for e in [ext.YMin,ext.XMin,ext.YMax,ext.XMax])
    print(bbox)
    return ext

"""This method has a municipality name as input, selects the mun. object in a municipality layer, and stores the single municipality into a shapefile"""
def getMunicipality(gemname, filen=r"C:\Temp\MTGIS\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM"):
    print ("Getting data for "+gemname)
    out = os.path.join(arcpy.env.workspace, gemname+'.shp')
    arcpy.MakeFeatureLayer_management(filen, 'municipalities_l')
    arcpy.SelectLayerByAttribute_management('municipalities_l', where_clause=fieldname+"= '"+gemname+"' ")
    arcpy.CopyFeatures_management('municipalities_l', out)
    return out

    """This method generates a shapefile of city neighborhoods that are within a municipality"""
def getCityNeighborhoods(buurtfile= "wijkenbuurten2017/buurt_2017", within = 'Utrecht.shp'):
    print ("Get city neighorhoods for "+within)
    out = os.path.join(arcpy.env.workspace, within.split('.')[0]+'buurten.shp')
    arcpy.MakeFeatureLayer_management(buurtfile, 'buurtenSourcel')
    arcpy.SelectLayerByLocation_management('buurtenSourcel', 'WITHIN', within)
    arcpy.CopyFeatures_management('buurtenSourcel', out)
    return out

"""This method aggregates a raster into a neighborhood shapefile using a Zonal mean, and stores it as a table"""
def aggRasterinNeighborhoods(raster, buurt = "buurten.shp"):
    print ("Aggregate "+raster +" into "+buurt)
    out = os.path.join(arcpy.env.workspace, os.path.splitext(os.path.basename(raster))[0]+'b.dbf')
    arcpy.gp.ZonalStatisticsAsTable_sa(buurt, "BU_CODE", raster, out, "DATA", "MEAN")
    return out


def main():
    #0) Setting computing environment
    arcpy.env.overwriteOutput = True #Such that files can be overwritten
    arcpy.env.workspace = r"C:\Temp\MTWEB" #Setting the workspace
    if arcpy.CheckExtension("Spatial") == "Available": #Check out spatial analyst extension
        arcpy.CheckOutExtension("Spatial")

    rs = arcpy.SpatialReference(28992)    #RD_New, GCS_Amersfoort


    ## 1: Getting data from Foursquare, store it as json and store as shapefile
    #First municipality
    municipality1 = getMunicipality("Utrecht", filen=r"C:\Temp\MTWEB\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM")
    city1 = 'Utrecht, NL'
    #jsonfile1 = getFSPlaces(city=city1, section='food', limit=50)
    jsonfile1 = os.path.join(arcpy.env.workspace,'Utrecht, NLfoodfsdata.json')
    result1shp = os.path.join(arcpy.env.workspace,r"result1.shp")
    d = loadJson(jsonfile1)
    json2SHP(d, result1shp,['cat','rating'],rs)




    #Second municipality
    municipality2 = getMunicipality("Zwolle", filen=r"C:\Temp\MTWEB\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM")
    city2 = 'Zwolle, NL'
    #jsonfile2 = getFSPlaces(city=city2, section='food', limit=50)
    jsonfile2 = os.path.join(arcpy.env.workspace,'Zwolle, NLfoodfsdata.json')
    result2shp = os.path.join(arcpy.env.workspace,r"result2.shp")
    d = loadJson(jsonfile2)
    json2SHP(d, result2shp,['cat','rating'],rs)




    ## 2: Generating topics from webtexts, store it as json, and as shapefile
    jsonfile = os.path.join(arcpy.env.workspace,'result.json')
    joinJSON(jsonfile1,jsonfile2,jsonfile)
    texts,ids = getTexts(jsonfile,'webtext')   #Integrate several municipalieties
    topics = getTopics(texts,ids)
##    for id, topic in zip(ids, topics):
##        print str(id) +' '+ str(topic)
    outfile = os.path.join(arcpy.env.workspace,'webtopics.json')
    addJSON(jsonfile,topics, outfile, ids)

    tname = os.path.join(arcpy.env.workspace,r"webtopics.shp")
    d = loadJson(outfile)
    topicnames = topics[0].keys()
    keys = ['cat','rating']+ topicnames
    json2SHP(d, tname,keys,rs)


    ## 3: Geoprocessing points with topics

    #For 1st municipality
    arcpy.env.extent =  getExtentfromFile(result1shp)
    buurt1 = getCityNeighborhoods(buurtfile= "wijkenbuurten2017/buurt_2017.shp", within = municipality1)
    for t in  normalizeFieldList(topicnames):
        kdensrast = kdensityRaster(tname, 'U',t)
        #densrast = densityRaster(tname, 'U', t)
        densbuurt = aggRasterinNeighborhoods(kdensrast,buurt1) #aggregate means into neighborhoods

    #For 2nd municipality
    arcpy.env.extent =  getExtentfromFile(result2shp)
    buurt2 = getCityNeighborhoods(buurtfile= "wijkenbuurten2017/buurt_2017.shp", within = municipality2)
    for t in  normalizeFieldList(topicnames):
        kdensrast = kdensityRaster(tname, 'Z',t)
        #densrast = densityRaster(tname, 'U', t)
        densbuurt = aggRasterinNeighborhoods(kdensrast,buurt2) #aggregate means into neighborhoods










if __name__ == '__main__':
    main()

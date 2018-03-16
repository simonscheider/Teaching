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
    outfile=city+section+'fsdata.json'
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

def json2SHP(dictionary, outFC, keylist, rs):
     #This genereates the output feature class
        arcpy.CreateFeatureclass_management(os.path.dirname(outFC), os.path.basename(outFC), 'POINT', '', '', '', rs)

        # Join fields to the feature class, using ExtendTable, depending on the OSM tags that came with the loaded results
        print keylist
        ff = (lambda s: (str(arcpy.ValidateFieldName((s[0:4])+(s[-5:]) if len(s) >= 10 else s))).upper())
        #This makes sure the tag names are converted into valid fieldnames (of length 10 max), where the first and the last 5 characters are taken to build the string
        tag_fields = map(ff, keylist)
        print tag_fields

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





def main():
    #0) Setting computing environment
    arcpy.env.overwriteOutput = True #Such that files can be overwritten
    arcpy.env.workspace = r"C:\Temp\MTWEB" #Setting the workspace
    if arcpy.CheckExtension("Spatial") == "Available": #Check out spatial analyst extension
        arcpy.CheckOutExtension("Spatial")

    #1) Getting city municipality file for city outline (bounding box), and setting the processing extent
    #municipality = getMunicipality("Utrecht", filen=r"C:\Temp\MTWEB\wijkenbuurten2017\gem_2017.shp", fieldname = "GM_NAAM")
    #b = getBBfromFile(municipality)
    #bb = b[0] #Get the bounding box string in WGS 84
    #rs = b[1] #Get the reference system of the original municipality file
    #ext = b[2] #Get the extent object in the original reference system
    #arcpy.env.extent = ext  #Set the geoprocessing extent to the municipality outline in the origina


    #1) Getting Foursquare data as JSON for some municipality
    #jsonfile = getFSPlaces()

    #2) Extracting topics from texts

    jsonfile = os.path.join(arcpy.env.workspace,'Utrecht, NLfoodfsdata.json')
##    rs = arcpy.SpatialReference(28992)    #RD_New, GCS_Amersfoort
##    tname = os.path.join(arcpy.env.workspace,r"result.shp")
##    d = loadJson(jsonfile)
##    json2SHP(d, tname,['cat','rating'],rs)
    texts,ids = getTexts(jsonfile,'webtext')
    topics = getTopics(texts,ids)
##    for id, topic in zip(ids, topics):
##        print str(id) +' '+ str(topic)
    outfile = os.path.join(arcpy.env.workspace,'webtexttopics.json')
    addJSON(jsonfile,topics, outfile, ids)
    rs = arcpy.SpatialReference(28992)    #RD_New, GCS_Amersfoort

    tname = os.path.join(arcpy.env.workspace,r"webtopics.shp")
    d = loadJson(outfile)
    topicnames = topics[0].keys()
    keys = ['cat','rating']+ topicnames
    json2SHP(d, tname,keys,rs)






if __name__ == '__main__':
    main()

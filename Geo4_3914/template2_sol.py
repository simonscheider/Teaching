#-------------------------------------------------------------------------------
# Name:        Geo4_3914 template2 (solution)
# Purpose:     This template can be used to load and analyse urban infrastructure data from Foursquare
#               and to extract semantic topics from linked webtexts. It is meant for the course
#               Methods and Techniques Specialisation
#               GEOGRAPHIC ANALYSIS OF WEB TEXT RESOURCES (using Python)
#               at the department for Human Geography and Planning , Utrecht university

#
# Author:      Simon Scheider
#
# Created:     03/04/2018
# Copyright:   (c) simon 2018
# Licence:     CC BY
#-------------------------------------------------------------------------------

#These are the necessary Python modules

#Native libraries
import numbers
import os
import string
import re
import json

#Libraries that need to be installed from 3rd parties
import arcpy
import numpy

#... for Web scraping
import requests #This package is for accessing webpages over URLs
from bs4 import BeautifulSoup #This package scrapes HTML text

#... for NLP
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
from nltk.stem.snowball import DutchStemmer
from nltk import wordpunct_tokenize

#... for ML
from sklearn.feature_extraction.text import CountVectorizer
#This is the LDA Python library for topic modeling
import lda

#... for plotting and wordclouds
import matplotlib.pyplot as plt
from wordcloud import WordCloud


##Comments of this format denote missing Python code that you need to produce during the course


#   -----------------------------------------------
#   Methods for getting and storing Foursquare data from the web and for web scraping (loading texts from web documents)

"""This method obtains Foursquare data (json) from the "explore" endpoint for a city and a thematic section and returns it as a dictionary"""
def getFSdata(url = 'https://api.foursquare.com/v2/venues/explore', city = 'Utrecht, NL', section='food', limit=None):
    #See: https://developer.foursquare.com/docs/api/venues/explore
        params = dict(
          client_id='VD5JRI5HLXSD21ZJUALG0K4BJOAVJNBIUXUNJDSDHERAYSA0',
          client_secret='J3SNUNCWZ4NCJU1YLP211M4K5ATSBEYRT12VFPNXC4RMYQ5Z',
          near = city,              #the city that is queried
          section = section,        #The theme
          v = '20170801' ,           #The temporal version of data
          limit=50                #The upper limit of results that can be get at once (this is always 50)
        )
        count = 0
        total = 50
        venues = []
        #This gets all results present at Foursquare and up to a limit, if that limit is given as input to the method
        while  count < total:
            params['offset'] = count
            resp = requests.get(url=url, params=params)
            data = json.loads(resp.text)
            venues += (data['response']['groups'][0])['items']
            t = data['response']['totalResults']
            total =  (t if limit == None else (t if t<limit else limit))
            count = len(venues)
        print 'Number of venues obtained for '+city +': '+str(count)
        return venues


"""This method takes a web address and scrapes its content via http"""
def scrape(url):
    resultobject = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
    try:
        page = requests.get(url, headers=headers)
    except requests.exceptions.ConnectionError, e:
        print("retry")
        print e
        try:
            page = requests.get(url, headers=headers)
        except:
            print("request of website "+url+' not successful! Skip.')
            return None


    soup = BeautifulSoup(page.content, 'lxml')

    resultobject['text']=  clean(soup)

    return resultobject


"""This method takes a html soup and turns Html code into cleaned text"""
def clean(soup):
    # kill all script and style elements and all links
    for script in soup(["script", "style", "a"]):
        script.extract()    # rip it out
    text = soup.get_text()
    text = text.replace('\n', ' ').replace('\r', '')
    text = re.sub(r'[?|$|.|!]',r'',text)
    text = re.sub(r'[^a-zA-Z]',r' ',text)

    # break into lines and remove leading and trailing space on each
    lines = (line for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = ' '.join(chunk for chunk in chunks if chunk)
    #print(text)
    return text


"""This method processes Foursquare data given as a dictionary (recommendedvenues), enriches it with web texts, and stores it as a jsonfile (outfile).
It loads
- place name ('Name')
- a homepage ('url') of a venue (if present), then uses the URL to scrape and enrich with webtexts ('webtext'),
- user ratings  ('rating')
- lat lon coordinates,   ('lat', 'lon')
- place category,  ('cat')
- menu texts ('menutext')
- tips.  ('tips')
Everything is stored in a json file (outfile) with approprate keys, as mentioned above in brackets.
"""
def processFSPlaces(recommendedvenues, outfile):
    out =[]
    #outfile=os.path.join(arcpy.env.workspace, city+section+'fsdata.json')
    with open(outfile, 'w') as fp:
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
                wt = scrape(url)
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
                        wt = scrape(menuurl)
                        if wt !=None:
                            p['menutext'] =  wt['text']
            tips = tryKeys(v, 'tips')
            if not isinstance(tips, Exception):
                texts = [t['text'] for t in tips]
                tt = ''
                for t in texts:
                        tt= tt+ '; ' +t
                #print 'Tips: '+'| '.join([text+' ('+findLanguage(text)+ ')' for text in texts])
                p['tips']  = tt
            out.append(p)
            fp.seek(0)
            json.dump(out, fp)
    fp.close()
    return outfile

"""Tries out keys on a dictionary object and captures key errors"""
def tryKeys(o, k1):
    try:
        out = o[k1]
        return out
    except Exception, e:
        print 'key error:'+str(e)
        return e

"""Tries to guess the language of a text (this can be used to automate text processing with NLP using the right wordbook)"""
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




#   -----------------------------------------------
#   Methods for loading and storing json data, and for turning it into (shp) geodata

"""A method for loading a jsonfile into a dictionary object"""
def loadJson(jsonfile):
     with open(jsonfile) as data:
        dic = json.load(data)
        data.close()
        return  dic

"""A method for writing a dictionary object into a json file"""
def writeJson(dictionary, outfile):
     with open(outfile, 'w') as fp:
        fp.seek(0)
        json.dump(dictionary, fp)
        fp.close()

"""A method for adding a list of dictionary objects (one by one) to the elements of a jsonfile (=list of objects), storing the results into another json file"""
def joinJSON(jsonfile,diclist, outjson, ids = None):
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

"""A method for merging two json files (lists of objects) into a single file"""
def addJSON(jsonfile1, jsonfile2,outfile):
    j1 = loadJson(jsonfile1)
    j2 = loadJson(jsonfile2)
    writeJson(j1 + j2,outfile)
    return outfile

"""Creates an arcpy geometry object from WGS 84 coordinates given in a dictionary"""
def createGeometry(element, rs):
    geom = arcpy.PointGeometry(arcpy.Point(float(element['lon']), float(element['lat'])),arcpy.SpatialReference(4326)).projectAs(rs)
    return geom

"""Validates and normalizes a list of strings as ArcGIS fields (attribute names)"""
def normalizeFieldList(keylist):
        print keylist
        ff = (lambda s: (str(arcpy.ValidateFieldName((s[0:4])+(s[-5:]) if len(s) >= 10 else s))).upper())
        #This makes sure the tag names are converted into valid fieldnames (of length 10 max), where the first and the last 5 characters are taken to build the string
        tag_fields = map(ff, keylist)
        print tag_fields
        return tag_fields

"""Turns a dictionary containing geodata (with lat lon coordinates and other key value tags given in keylist) into a shapefile"""
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



#   -----------------------------------------------
#   Methods for processing texts with NLP and LDA

"""Method for extracting a list of texts from a jsonfile using a certain key (if key is not existing, leaves it out, and delivers also an index)"""
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

""" Method turns a given text into tokens removing stopwords and stemming them."""
def tokenize(text, language = 'dutch'):

    if language == 'dutch':
        p_stemmer = DutchStemmer()
    else:
        p_stemmer = PorterStemmer()

    text = text.lower()
    stop = set(stopwords.words(language))
    tokens = nltk.word_tokenize(text)
    tokens = [i for i in tokens if i not in string.punctuation and len(i)>=3]
    tokens = [i for i in tokens if i not in stop]  #Removing stopwords
    tokens = [i for i in tokens if i.isalpha() and 'www' not in i]    #Removing numbers and alphanumeric characters and www
    tokens = [p_stemmer.stem(i) for i in tokens]   #Stemming
    return tokens


"""This method fits an LDA model to a list of texts, prints out most probable words for each topic, and returns topic probabilities for each text (identified by its title)"""
def getTopics(texts, titles,language = 'dutch', showwordcloud = False):

    #This is where the texts are turned into a document-term matrix. Also a vectorizer is used to get the list of words used in the model (vocabulary)
    vectorizer = CountVectorizer(min_df = 1, stop_words = stopwords.words(language), analyzer = 'word', tokenizer=tokenize)
    X = vectorizer.fit_transform(texts)
    #Gets the vocabulary of stemmed words (terms)
    vocab = vectorizer.get_feature_names()
    print(vocab)
    print('vocabulary size: '+str(len(vocab)))
    print('Size of document-term matrix:'+str(X.shape))

    #This computes the LDA model
    model = lda.LDA(n_topics=10, n_iter=600, random_state=300)
    model.fit(X)
    topic_word = model.topic_word_
    print("shape: {}".format(topic_word.shape))
    #plt.plot(model.loglikelihoods_[5:])
    #plt.show()

    # get the top 10 words for each topic and visualize them (by probablity)
    n = 10
    for i, topic_dist in enumerate(topic_word):
        sortedindex = numpy.argsort(topic_dist)
        topic_words = numpy.array(vocab)[sortedindex][:-(n+1):-1]
        word_freq = numpy.array(topic_dist)[sortedindex][:-(n+1):-1]
        frequencies = dict(zip(topic_words, word_freq))
        print('*Topic {}\n- {}'.format(i, ' '.join(topic_words)))
        if showwordcloud:
            plt.figure()
            plt.imshow(WordCloud().fit_words(frequencies))
            plt.axis("off")
            plt.title("Topic #" + str(i))
            plt.show()
    #return model
    # apply topic model to new test data set and write topics into feature vector
    doc_topic_test = model.transform(X)
    #print(doc_topic_test)
    i = 0
    result = []
    for title, topics in zip(titles, doc_topic_test):
        title =str(title).encode('utf-8')
        print("Venue {} (top topic: {})".format(title, topics.argmax()))
        f = {}
        for j,t in enumerate(topics):
                f['topic '+str(j)]= t
        result.append(f)
        i+=1
    return result



#   -----------------------------------------------
#   Methods for processing geodata

"""This method has a municipality name as input, selects the mun. object in a municipality layer, and stores the single municipality into a shapefile"""
def getMunicipality(gemname, filen=r"C:\Temp\MTGIS\wijkenbuurten2014\gem_2014.shp", fieldname = "GM_NAAM"):
    print ("Getting data for "+gemname)
    out = os.path.join(arcpy.env.workspace, gemname+'.shp')
    arcpy.MakeFeatureLayer_management(filen, 'municipalities_l')
    arcpy.SelectLayerByAttribute_management('municipalities_l', where_clause=fieldname+"= '"+gemname+"' ")
    arcpy.CopyFeatures_management('municipalities_l', out)
    return out

"""This method has a (municipality) shapefile as input, then gets its reference system (rs), gets the first geometry's extent, reprojects it to WGS 84, and returns a bbox, the rs and the extent"""
def getExtentfromFile(filen):
    print ("Getting BB")
    ext = arcpy.Describe(filen).extent
    bbox = ", ".join(str(e) for e in [ext.YMin,ext.XMin,ext.YMax,ext.XMax])
    print(bbox)
    return ext

"""This method generates a kernel density raster from a point shapefile"""
def kdensityRaster(shapefile, mun, populationfield):
    print ("Generate kernel density raster")
    out = os.path.join(arcpy.env.workspace, mun+'kdr'+populationfield)
    outKDens = arcpy.sa.KernelDensity(shapefile, populationfield, 50, 500,"SQUARE_KILOMETERS")
    outKDens.save(out)
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



#------------------------------------------------------------------------------------

"""This is the main procedure that this script is supposed to carry out. Each line is a processing step.
The result are city neighborhood files (tables) for each topic that can be mapped and which shows the mean accessibility of the topic found at places within in a city"""
def main():

    # 0: Setting computing environment
    arcpy.env.overwriteOutput = True #Such that files can be overwritten
    arcpy.env.workspace = r"C:\Temp\MTWEB" #Setting the workspace
    if arcpy.CheckExtension("Spatial") == "Available": #Check out spatial analyst extension
        arcpy.CheckOutExtension("Spatial")
    rs = arcpy.SpatialReference(28992)    #Getting reference system for RD_New, GCS_Amersfoort to project geodata


    # 1: Getting data from Foursquare, store it as json and  as shapefile

    #First municipality
    jsonfile1 = os.path.join(arcpy.env.workspace,'Utrechtfoodfsdata.json')
    municipality1 = getMunicipality("Utrecht", filen=r"C:\Temp\MTWEB\wijkenbuurten2014\gem_2014.shp", fieldname = "GM_NAAM")
    city1 = 'Utrecht, NL'
    fsdata1 = getFSdata(city=city1, section='food')
    processFSPlaces(fsdata1, jsonfile1)
    result1shp = os.path.join(arcpy.env.workspace,"Utrechtfood.shp")
    d = loadJson(jsonfile1)
    json2SHP(d, result1shp,['cat','rating'],rs)

    #Second municipality
    jsonfile2 = os.path.join(arcpy.env.workspace,'Zwollefoodfsdata.json')
    municipality2 = getMunicipality("Zwolle", filen=r"C:\Temp\MTWEB\wijkenbuurten2014\gem_2014.shp", fieldname = "GM_NAAM")
    city2 = 'Zwolle, NL'
    fsdata2 = getFSdata(city=city2, section='food')
    processFSPlaces(fsdata2, jsonfile2)
    result2shp = os.path.join(arcpy.env.workspace,"Zwollefood.shp")
    d = loadJson(jsonfile2)
    json2SHP(d, result2shp,['cat','rating'],rs)


    # 2: Generating topics from webtexts, store it as json, and as shapefile

    jsonfile = os.path.join(arcpy.env.workspace,'result.json')
    addJSON(jsonfile1,jsonfile2,jsonfile)                           #This adds the two jsonfiles from two municipalities into a single one
    texts,ids = getTexts(jsonfile,'webtext')                        #This loads the texts contained a certain key
    topics = getTopics(texts,ids,language = 'dutch', showwordcloud=False)                                   #This method runs LDA to get topic probabilities for each loaded text
    outfile = os.path.join(arcpy.env.workspace,'webtopics.json')
    joinJSON(jsonfile,topics, outfile, ids)                         #This joins the topic probabilities and the json file (for those places having texts)

    topicshp = os.path.join(arcpy.env.workspace,r"webtopics.shp")       #This stores the topics into a single shapefile
    d = loadJson(outfile)
    topicnames = topics[0].keys()
    keys = ['cat','rating']+ topicnames
    json2SHP(d, topicshp, keys, rs)


    # 3: Geoprocessing points with topics

    #For 1st municipality, generates neighborhood file. Then generates an accessibility raster (density) for each topic and  aggregates it into a neighborhood table
    arcpy.env.extent =  getExtentfromFile(result1shp)
    buurt1 = getCityNeighborhoods(buurtfile= "wijkenbuurten2014/buurt_2014.shp", within = municipality1)
    for t in  normalizeFieldList(topicnames):
        kdensrast = kdensityRaster(topicshp, 'U',t)
        densbuurt = aggRasterinNeighborhoods(kdensrast,buurt1) #aggregate means into neighborhoods

    #For 2nd municipality,  generates neighborhood file. Then generates an accessibility raster (density) for each topic and aggregates it into a neighborhood table
    arcpy.env.extent =  getExtentfromFile(result2shp)
    buurt2 = getCityNeighborhoods(buurtfile= "wijkenbuurten2014/buurt_2014.shp", within = municipality2)
    for t in  normalizeFieldList(topicnames):
        kdensrast = kdensityRaster(topicshp, 'Z',t)
        densbuurt = aggRasterinNeighborhoods(kdensrast,buurt2) #aggregate means into neighborhoods







if __name__ == '__main__':
    main()

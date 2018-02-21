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





import json, requests
from nltk.corpus import stopwords
from nltk import wordpunct_tokenize
import placewebscraper


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



def main():
    getFSPlaces()




if __name__ == '__main__':
    main()

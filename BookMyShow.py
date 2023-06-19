#!/usr/bin/env python3

import requests
import pdb
import sys

import subprocess
from bs4 import BeautifulSoup
from sys import exit
from time import time
from time import sleep
from re import sub as reSub
from re import compile as reCompile
from datetime import datetime
from json import loads
from sys import stdout
from os import system
from os import remove
from random import randint
from random import randrange
from argparse import ArgumentParser
from argparse import Action
from os.path import expanduser
from os.path import exists
from threading import Thread
from playsound import playsound
from typing import List
from bmsDecorator import debug
from bmsTypes import BMSRegion, City, BMSVenue, Venue
from collections import OrderedDict

def getObject():
    return type( '', (), {} ) # returns a simple object that can be used to add attributes

class NotificationThread( Thread ):
    def __init__( self, title, message, args ):
        Thread.__init__( self )
        self.title = title
        self.message = message
        self.args = args
        self.interval = 10 # will show desktop notification at this intervals ( seconds )

    def run( self ):
        if self.args.pushBullet:
            token = self.args.pushBullet[ 0 ]
            if len( self.args.pushBullet ) > 1:
                deviceList = self.args.pushBullet[ 1: ]
            else:
                # send to all devices
                deviceList = [ None ]
            configFilePath = expanduser( '~' ) + '/.ntfy.yml'
            for device in deviceList:
                with open( configFilePath, 'w+' ) as ntfyFile:
                    # set up config to push to given device
                    ntfyFile.write( 'backends: ["pushbullet"]\n' )
                    ntfyFile.write( 'pushbullet: {"access_token": "' + token + '"' )
                    if device is not None:
                        ntfyFile.write( ', "device_iden": "' + device + '"' )
                    ntfyFile.write( '}' )
                cmd = 'ntfy -t "{0}" send "{1}"'.format( self.title, self.message)
                system( cmd )
            if exists( configFilePath ):
                # we don't need this config anymore
                remove( configFilePath )
        while True:
            # Keep on sending desktop notifications till the program is closed
            start = time()
            cmd = 'ntfy -t "{0}" send "{1}"'.format( self.title, self.message)
            system( cmd )
            stop = time()
            timeRemaining = self.interval - ( stop - start )
            timeRemaining = int( round( timeRemaining if timeRemaining > 0 else 0 ) )
            sleep( timeRemaining )
        
class BMS( object ):

    def __init__( self, args ):
        self.args = args
        self.regionCode = self.args.regionCode.upper()
        self.date = self.args.date
        self.cinema = self.args.cinema
        self.movie = self.args.movie
        self.format = self.args.format
        self.alarm = self.args.alarm
        self.title = ''
        self.city: City = None
        self.ss = requests.session()
        self.ss.headers.update(
            {
                # 'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                # 'Accept-Encoding': "gzip, deflate, br",
                # 'Accept-Encoding': "identity",
                # 'Host': "in.bookmyshow.com",
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36',
                # 'Connection': 'Keep-Alive'
            }
        )
        # self.ss.get( "https://in.bookmyshow.com/explore/movies-bengaluru" )
        # self.setRegionDetails( self.regionCode )

    def notification( self, title, message ):
        nThread = NotificationThread( title, message, self.args )
        nThread.start()
        # the thread will run till eternity or unless terminated using Ctrl-C

    def ringSineBell( self ):
        totalDuration = 0.0
        while totalDuration < 10.0:
            duration = 1.0 / randint(5,10)  # seconds
            freq = randrange( 200, 2000, 200 )  # Hz
            system('play --no-show-progress --null --channels 1 synth {} sine {}'.format(duration, freq))
            totalDuration += duration

    def ringBell( self ):
        totalDuration = 0.0
        while totalDuration < 8 * 60 * 60: # 8 hours
            duration = 1.0 / randint(5,10)  # seconds
            print( '\a', end="\r" )
            sleep( duration )
            totalDuration += duration

    def soundAlarm( self ):
        if self.alarm is not None:
            self.alarm = self.alarm.strip()
            if self.alarm.find( "~" ) == 0:
                # need to pass absolute path for home directory
                self.alarm = expanduser( '~' ) + self.alarm[ 1: ]
            while True:
                playsound( self.alarm )
        else:
            self.ringBell()

    def fetchVenues( self ) -> BMSVenue:
        '''
        Returns all available regions
        '''
        url = f"https://in.bookmyshow.com/pwa/api/de/venues?regionCode={self.city.RegionCode}&eventType=MT"
        cmd = [
            "curl",
            "--http1.1",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            url
        ]
        data = subprocess.run( cmd, capture_output=True, text=True )
        return BMSVenue.parse_raw( data.stdout )

    def searchVenue( self, region: str ) -> List[Venue]:
        venues = self.fetchVenues()
        results = []
        
        for item in venues.BookMyShow.arrVenue:
            if (
                ( region.lower() in item.VenueCode.lower() ) or
                ( region.lower() in item.VenueName.lower() )
            ):
                results.append(item)
        
        return results
        
    def fetchRegions( self ) -> BMSRegion:
        '''
        Returns all available regions
        '''
        url = "https://in.bookmyshow.com/api/explore/v1/discover/regions"
        cmd = [
            "curl",
            "--http1.1",
            "--user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            url
        ]
        data = subprocess.run( cmd, capture_output=True, text=True )
        return BMSRegion.parse_raw( data.stdout )

    def searchRegion( self, region: str ) -> List[City]:
        regions = self.fetchRegions()
        results = []
        
        def checkItem( cities: List[City] ):
            for item in cities:
                if (
                    ( region.lower() in item.RegionCode.lower() ) or
                    ( region.lower() in item.RegionName.lower() ) or
                    ( any( region.lower() in a.lower() for a in item.Alias ) )
                ):
                    results.append(item)
                    
        checkItem( regions.BookMyShow.TopCities )
        checkItem( regions.BookMyShow.OtherCities )
        
        return results
    
    def setRegion( self, city: City ):
        self.city = city

    def getSearchUrl( self, searchTerm ):
        curTime = int( round( time() * 1000 ) )
        url = "https://in.bookmyshow.com/quickbook-search.bms?d[mrs]=&d[mrb]=&cat=&_=" + str( curTime ) + "&q=" + searchTerm.replace( " ", "+" ) + "&sz=8&st=ON&em=&lt=&lg=&r=" + self.regionData.get( "code" ) + "&sr="
        return url

    def getMovieUrl( self, movieData ):
        '''
        `movieData` is similar to below:

        {'ST': 'NS', 'GRP': 'Event', 'IS_NEW': False, 'L_URL': '', 'DESC': ['Chris Evans', ' Robert Downey Jr.'], 'CODE': 'EG00068832', 'REGION_SLUG': '', 'EVENTSTRTAGS': [], 'IS_TREND': False, 'RATING': '', 'WTS': '9,14,847', 'TITLE': 'Avengers: Endgame', 'ID': 'ET00090482', 'TYPE': 'MT', 'TYPE_NAME': 'Movies', 'CAT': ''}
        '''

        curDate = datetime.now().strftime("%Y%m%d") if self.date is None else self.date
        movieName = reSub('[^0-9a-zA-Z ]+', '', movieData.get('TITLE') ).lower().replace( " ", "-" )

        movieUrl = "https://in.bookmyshow.com/buytickets/"
        movieUrl += movieName
        movieUrl += "-" + self.regionData.get( 'alias' ) + "/movie-" + self.regionData.get( 'code' ).lower() + "-"
        movieUrl += movieData.get( 'ID' )
        movieUrl += "-MT/"
        movieUrl += curDate
        return movieUrl

    def getCinemaUrl( self, cinemaData ):
        '''
        `cinemaData` is similar to below:

        {"CC":"PVR","ST":"NS","REGION_SLUG":"","GRP":"Venue","EVENTSTRTAGS":[],"RATING":"","L_URL":"","WTS":"","TITLE":"PVR: Forum Mall, Koramangala","ID":"PVBN","TYPE_NAME":"Venues","TYPE":"|MT|","CAT":""}
        '''

        curDate = datetime.now().strftime("%Y%m%d") if self.date is None else self.date
        cinemaName = reSub('[^0-9a-zA-Z ]+', '', cinemaData.get('TITLE') ).lower().replace( " ", "-" )

        cinemaUrl = "https://in.bookmyshow.com/buytickets/"
        cinemaUrl += cinemaName
        cinemaUrl += "/cinema-" + self.regionData.get( 'code' ).lower() + "-"
        cinemaUrl += cinemaData.get( 'ID' )
        cinemaUrl += "-MT/"
        cinemaUrl += curDate
        return cinemaUrl

    def getUrlDataJSON( self, searchTerm ):
        '''
        returns all matched results after searching on bms
        '''

        url = self.getSearchUrl( searchTerm )
        headers = {
                'x-requested-from' : 'WEB',
        }
        data = self.ss.get( url, headers=headers )
        assert data.status_code == 200
        jsonResp = data.json()
        return jsonResp

    def search( self, searchTerm, typeName="Movies" ):
        jsonResp = self.getUrlDataJSON( searchTerm )
        # return the first hit belonging to typeName
        data = {}
        for movieInfo in jsonResp[ 'hits' ]:
            if movieInfo.get( 'TYPE_NAME' ) == typeName:
                data = movieInfo
                break
        
        url = None
        if typeName == "Movies":
            if data.get( 'SHOWDATE' ) is None:
                # Check if show is on
                print( "The show counters are yet to be opened!" )
                return None
            url = self.getMovieUrl( data )
        elif typeName == "Venues":
            url = self.getCinemaUrl( data )
        self.title = data.get( 'TITLE', '' )

        return url
    
    def checkAvailability( self, movieLink ):
        '''
        movieLink refers to moviePage where we have information about the movie, the cast and other stuff
        '''
        pass

    def checkCinemaAvailability( self, cinemaLink, movieName ):
        '''
        Notifies if a show is available in your requested cinema
        '''
        cinemaDetails = self.ss.get( cinemaLink )
        if not ( cinemaDetails.url == cinemaLink ):
            print( "Counters haven't opened for specified date yet, retrying..." )
            return False
        assert cinemaDetails.status_code == 200
        cinemaSoup = BeautifulSoup( cinemaDetails.content, 'html5lib' )
        # get movie name
        jsonRespOfMovies = self.getUrlDataJSON( movieName )
        # return the first hit belonging to movieName
        data = {}
        for movieInfo in jsonRespOfMovies[ 'hits' ]:
            if movieInfo.get( 'TYPE_NAME' ) == "Movies":
                data = movieInfo
                break
        movieName = data.get( 'TITLE', movieName )
        
        scripts = cinemaSoup.find_all( "script" )
        jsonMoviePattern = reCompile( "^\s*try\s+{\s+var\s+API\s+=\s+JSON.parse\(\"(.*)\"\);" )
        jsonMovieFormats = {}
        for script in scripts:
            jsonMovieFormats = jsonMoviePattern.match( str( script.string ) )
            if jsonMovieFormats:
                jsonMovieFormats = jsonMovieFormats.groups()[ 0 ]
                # now remove double slashes
                jsonMovieFormats = jsonMovieFormats.replace( "\\", "" )
                # now convert to json
                jsonMovieFormats = loads( jsonMovieFormats )
                break

        # now see if your format is available
        found = False
        if jsonMovieFormats['BookMyShow']['Event']:
            for event in jsonMovieFormats['BookMyShow']['Event']:
                if event.get( 'EventTitle' ) == movieName:
                    for eventFormat in event[ 'ChildEvents' ]:
                        if self.format is None:
                            # movie is available in any format
                            found = True
                            break
                        elif eventFormat[ 'EventDimension' ] == self.format:
                            # we found our format
                            found = True
                            break

        # string to print format if available
        formatAvailable = ""
        if self.format is not None:
            formatAvailable = " in " + self.format

        if found:
            # Movie tickets are now available
            print( "HURRAY! Movie tickets are now available" + formatAvailable )
            self.notification( "Hurray!", "Tickets for " + movieName + " at " + self.title + " are now available" + formatAvailable )
            self.soundAlarm()
            return True
        elif jsonMovieFormats['BookMyShow']['Event']:
            # The requires format isn't available or the movie is yet to be released
            availableFormats = [ eventFormat[ 'EventDimension' ] for eventFormat in event[ 'ChildEvents' ] for event in jsonMovieFormats['BookMyShow']['Event'] if event[ 'EventTitle' ] == movieName ]
            if availableFormats:
                print( "The available format(s) : " + ( ", ".join( availableFormats ) ) )
                print( "Movie is not available in requested " + self.format + " format, will retry..." )
                return False
            else:
                print( "Movie tickets aren't available yet, retrying..." )
                return False
        else:
            print( "Movie tickets aren't available yet, retrying..." )
            return False

    def checkMovie( self, name ):
        movieLink = self.search( name )
        if movieLink is None:
            exit( 0 )
        self.checkAvailability( movieLink )

    def checkCinema( self ):
        cinemaLink = self.search( self.cinema, typeName="Venues" )
        if cinemaLink is None:
            exit( 0 )
        return self.checkCinemaAvailability( cinemaLink, self.movie )

def parser():
    parser = ArgumentParser( prog=sys.argv[ 0 ],
                             description="A script to check if tickets are available for the movie in the specified cinema at a given date",
                             epilog="And you will be the first one to be notified as soon as the show is available" )
    parser.add_argument( '-m', '--movie', required=True, action='store', type=str, help="The movie you're looking to book tickets for" )
    parser.add_argument( '-c', '--cinema', required=True, action='store', type=str, help="The cinema in which you want to watch the movie" )
    parser.add_argument( '-f', '--format', action='store', choices=[ "2D", "3D", "IMAX 2D", "IMAX 3D" ], type=str, help="Preferred format, if any" )
    parser.add_argument( '-d', '--date', required=True, action='store', type=str, help="Format: YYYYMMDD | The date on which you want to book tickets." )
    parser.add_argument( '-r', '--regionCode', required=True, action='store', type=str, help="The region code of your area; BANG for Bengaluru" )
    parser.add_argument( '-i', '--interval', action='store', type=int, help="BMS server will be queried every interval seconds", default=60 )
    parser.add_argument( '-a', '--alarm', action='store', type=str, help="Path to audio file that will play as an alarm when notified ( optional )" )
    parser.add_argument( '-b', '--pushBullet', action='store', metavar=( "ACCESS_TOKEN", "DEVICE_ID" ), type=str, nargs='+', help="Send notification to your device using pushbullet" )
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parser()
    interval = args.interval
    status = False
    while not status:
        start = time()
        retry = 0
        while retry < 60:
            # only retry for some time on connectivity issues
            # bms = BookMyShow( args )
            # status = bms.checkCinema()
            try:
                bms = BMS( args )
                region = bms.searchRegion( args.regionCode )[ 0 ]
                region = [ item.RegionCode.lower() for item in region ]
                bms.setRegion( region )
                venue = bms.searchVenue( args.cinema )[ 0 ]
                print( 'Venue', venue )
                # status = bms.checkCinema()
                sys.exit( 1 )
                break
            except AssertionError:
                print( "Seems like we lost the connection mid-way, will retry..." )
                retry += 1
            except KeyboardInterrupt:
                sys.exit( 1 )
            except Exception as e:
                print( "Something unexpected happened; Recommended to re-run this script with correct values" )
                print( "Printing traceback:" )
                print( e )
                break
        if not status:
            try:
                stop = time()
                timeRemaining = interval - ( stop - start )
                timeRemaining = int( round( timeRemaining if timeRemaining > 0 else 0 ) )
                sleep( timeRemaining )
            except KeyboardInterrupt:
                sys.exit( 1 )
            except Exception as e:
                print( "Something unexpected happened; Recommended to re-run this script with correct values" )
                break

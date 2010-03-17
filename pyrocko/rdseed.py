import logging

import orthodrome, trace, pile, config, model, eventdata, io
import os, sys, shutil, subprocess, tempfile, calendar, time

pjoin = os.path.join

logger = logging.getLogger('pyrocko.rdseed')

def dumb_parser( data ):
    
    (in_ws, in_kw, in_str) = (1,2,3)
    
    state = in_ws
    
    rows = []
    cols = []
    accu = ''
    for c in data:
        if state == in_ws:
            if c == '"':
                new_state = in_str
                
            elif c not in (' ', '\t', '\n', '\r'):
                new_state = in_kw
        
        if state == in_kw:
            if c in (' ', '\t', '\n', '\r'):
                cols.append(accu)
                accu = ''
                if c in ('\n','\r'):
                    rows.append(cols)
                    cols = []
                new_state = in_ws
                
        if state == in_str:
            if c == '"':
                accu += c
                cols.append(accu[1:-1])
                accu = ''
                if c in ('\n','\r'):
                    rows.append(cols)
                    cols = []
                new_state = in_ws
        
        state = new_state
    
        if state in (in_kw, in_str):
             accu += c
    if len(cols) != 0:
       rows.append( cols )
       
    return rows

class Programs:
    rdseed   = 'rdseed4.8'

class SeedVolumeNotFound(Exception):
    pass

class SeedVolumeAccess(eventdata.EventDataAccess):

    def __init__(self, seedvolume, datapile=None):
        
        '''Create new SEED Volume access object.
        
        In:
            seedvolume -- filename of seed volume
            datapile -- if not None, this should be a pyrocko.pile.Pile object 
                with data traces which are then used instead of the data
                provided by the SEED volume. (This is useful for dataless SEED
                volumes.)
        '''
    
        eventdata.EventDataAccess.__init__(self, datapile=datapile)
        self.tempdir = None
        self.seedvolume = seedvolume
        if not os.path.isfile(self.seedvolume):
            raise SeedVolumeNotFound()
        
        self.tempdir = tempfile.mkdtemp("","SeedVolumeAccess-")
        self._unpack()

    def __del__(self):
        import shutil
        if self.tempdir:
            shutil.rmtree(self.tempdir)
                
    def get_pile(self):
        if self._pile is None:
            fns = io.save( io.load(pjoin(self.tempdir, 'mini.seed')), pjoin(self.tempdir,
                     'raw-%(network)s-%(station)s-%(location)s-%(channel)s.mseed'))
                
            self._pile = pile.Pile()
            self._pile.add_files(fns)
            
        return self._pile
        
    def get_restitution(self, tr):
        respfile = pjoin(self.tempdir, 'RESP.%s.%s.%s.%s' % tr.nslc_id)
        trans = trace.InverseEvalresp(respfile, tr)
        return trans
        
    def _unpack(self):
        input_fn = self.seedvolume
        output_dir = self.tempdir

        def strerr(s):
            return '\n'.join([ 'rdseed: '+line for line in s.splitlines() ])
                
        # seismograms:
        if self._pile is None:
            rdseed_proc = subprocess.Popen([Programs.rdseed, '-f', input_fn, '-d', '-z', '3', '-o', '4', '-p', '-R', '-q', output_dir], 
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (out,err) = rdseed_proc.communicate()
            logging.info(strerr(err))
        
        # event data:
        rdseed_proc = subprocess.Popen([Programs.rdseed, '-f', input_fn, '-e', '-q', output_dir], 
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err) = rdseed_proc.communicate()
        logging.info(strerr(err) )
        
        # station summary information:
        rdseed_proc = subprocess.Popen([Programs.rdseed, '-f', input_fn, '-S', '-q', output_dir], 
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out,err) = rdseed_proc.communicate()
        logging.info(strerr(err))
        
        # station headers:
        rdseed_proc = subprocess.Popen([Programs.rdseed, '-f', input_fn, '-s', '-q', output_dir], 
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
        (out,err) = rdseed_proc.communicate()
        fout = open(os.path.join(output_dir,'station_header_infos'),'w')
        fout.write( out )
        fout.close()
        logging.info(strerr(err))
        
    def _get_events_from_file( self ):
        rdseed_event_file =  os.path.join(self.tempdir,'rdseed.events')
        if not os.path.isfile(rdseed_event_file):
            return []
        
        f = open(rdseed_event_file, 'r')
        events = []
        for line in f:
            toks = line.split(', ')
            if len(toks) == 9:
                datetime = toks[1].split('.')[0]
                lat = toks[2]
                lon = toks[3]
                format = '%Y/%m/%d %H:%M:%S'
                secs = calendar.timegm( time.strptime(datetime, format))
                e = model.Event(
                    lat = float(toks[2]),
                    lon = float(toks[3]),
                    depth = float(toks[4])*1000.,
                    magnitude = float(toks[8]),
                    time = secs
                )
                events.append(e)
            else:
                raise Exception('Event description in unrecognized format')
            
        f.close()
        return events
            
    def _get_stations_from_file(self):
        
        
        # make station to locations map, cause these are not included in the 
        # rdseed.stations file
        
        p = self.get_pile()
        ns_to_l = {}
        for nslc in p.nslc_ids:
            ns = nslc[:2]
            if ns not in ns_to_l:
                ns_to_l[ns] = set()
            
            ns_to_l[ns].add(nslc[2])
        
        
        rdseed_station_file = os.path.join(self.tempdir, 'rdseed.stations')
        
        f = open(rdseed_station_file, 'r')
        
        # sometimes there are line breaks in the station description strings
        
        txt = f.read()
        rows = dumb_parser( txt )
        f.close()
        
        icolname = 6
        icolcomp = 5
        
        stations = []
        for cols in rows:
            for location in ns_to_l[cols[1],cols[0]]:    
                s = model.Station(
                    network = cols[1],
                    station = cols[0],
                    location = location,
                    lat = float(cols[2]),
                    lon = float(cols[3]),
                    elevation = float(cols[4]),
                    name = cols[icolname],
                    components = set(cols[icolcomp].split())
                )
                stations.append(s)
                
        return stations
        

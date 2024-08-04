import os
import pandas as pd

from flask import Flask, request, jsonify
from daylight_window import DayLightWindow
from port_tide_window import TideWindow
from utils import Intervals
from datetime import datetime


FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# CSV FILE PATHS
TIDE_CSV_PATH = os.path.join(FILE_DIR, '..\\tide_heights.csv')
PORT_CSV_PATH = os.path.join(FILE_DIR, '..\\ports.csv')
VESSEL_CSV_PATH =os.path.join(FILE_DIR, '..\\vessels.csv')


class BerthWindow:
    def __init__(self):
        self.tide_df = pd.read_csv(TIDE_CSV_PATH)
        self.port_df = pd.read_csv(PORT_CSV_PATH)
        self.vessel_df = pd.read_csv(VESSEL_CSV_PATH)
        self.calibrate_tide()
        self.draught_mapping = self.build_vessel_draught_mapping()
        self.port_mapping = self.build_port_mapping()
        self.tide_window = TideWindow(self.tide_df)
        self.daylight_window = DayLightWindow(self.port_df)
    
    def calibrate_tide(self):
        self.tide_df = self.tide_df.merge(self.port_df[['NAME', 'APPROACH_MLLW_METERS']], 
                                          how='left',
                                          left_on='PORT_NAME',
                                          right_on='NAME')
        self.tide_df.fillna({'APPROACH_MLLW_METERS': 0})
        self.tide_df['TIDE_HEIGHT_MT'] = self.tide_df['TIDE_HEIGHT_MT'] + self.tide_df['APPROACH_MLLW_METERS'] 
    
    def build_port_mapping(self):
        return dict(zip(self.port_df['UNLOCODE'], self.port_df['NAME']))
    
    def build_vessel_draught_mapping(self):
        return dict(zip(self.vessel_df['IMO'].apply(lambda x: str(x)), self.vessel_df['DRAUGHT']))
    
    def find_tide_window(self, port_id: str, imo: str, arrival_time: datetime):
        port_name = self.get_port_name(port_id)
        draught = self.get_draught(imo)  
        return self.tide_window.find_tide_window(draught, port_name, arrival_time)
    
    def find_daylight_window(self, port_id: str, arrival_time: datetime) -> pd.DataFrame:
        port_name = self.get_port_name(port_id)
        return self.daylight_window.find_daylight_window(port_name, arrival_time)

    def find_tide_daylight_window(self, port_id: str, imo: str, arrival_time: datetime) -> pd.DataFrame:
        tide_window_df = self.find_tide_window(port_id, imo, arrival_time)
        daylight_window_df = self.find_daylight_window(port_id, arrival_time)
        
        tide_intervals = Intervals(list(tide_window_df.itertuples(index=False, 
                                                                  name=None)))
        tide_daylight_intervals = tide_intervals.intersect(list(daylight_window_df.itertuples(index=False, 
                                                                                              name=None)))
        return pd.DataFrame(tide_daylight_intervals, columns=['START_DATETIME', 'END_DATETIME'])
    
    def get_port_name(self, port_id:str):
        try:
            return self.port_mapping[port_id]  
        except KeyError:
            raise KeyError('Unknown port ID {}'.format(port_id)) 
    
    def get_draught(self, imo):
        try:
            return self.draught_mapping[imo]
        except KeyError:            
            raise KeyError('Unknown vessel IMO {}'.format(imo))
    
app = Flask(__name__)       

berth_window = BerthWindow()

@app.route('/tide_window', methods=['GET'])
def find_tide_window():
    port_id = request.args.get('port', default=None, type=str)
    imo = request.args.get('imo', default= None, type=str)
    
    # handle invalid parameters
    try:
        assert port_id is not None
        assert imo is not None
    except AssertionError:
        return err_msg('Parameter port and imo is needed in request', 400)
    arrival_time = request.args.get('arrival', default=None, type=str)
    
    try:
        if arrival_time is not None:
            arrival_time = datetime.strptime(arrival_time, '%Y-%m-%d:%H:%M:%S')
        else:
            arrival_time = datetime.now()
    except ValueError:
        return err_msg('incorrect arrival time format. Format like %Y-%m-%d:%H:%M:%S', 400)
    
    # call func
    try:
        df = berth_window.find_tide_window(port_id, imo, arrival_time)
    except Exception as e:
        return err_msg('Internal Error: ' + str(e), 500)
    
    return jsonify(data=df.to_dict(orient='index'), status=200) 

@app.route('/tide_daylight_window', methods=['GET'])
def find_tide_daylight_window():
    port_id = request.args.get('port', default=None, type=str)
    imo = request.args.get('imo', default= None, type=str)
    
    # handle invalid parameters
    try:
        assert port_id is not None
        assert imo is not None
    except AssertionError:
        return err_msg('Parameter port and imo is needed in request', 400)
    arrival_time = request.args.get('arrival', default=None, type=str)
    
    try:
        if arrival_time is not None:
            arrival_time = datetime.strptime(arrival_time, '%Y-%m-%d:%H:%M:%S')
        else:
            arrival_time = datetime.now()
    except ValueError:
        return err_msg('Incorrect arrival time format. Format like %Y-%m-%d:%H:%M:%S', 400)
    
    # call func
    try:
        df = berth_window.find_tide_daylight_window(port_id, imo, arrival_time)
    except Exception as e:
        return err_msg('Internal Error: ' + str(e), 500)
    
    return jsonify(data=df.to_dict(orient='index'), status=200) 

def err_msg(msg: str, err_code=200):
    return jsonify(data={'error': msg}, status=err_code)
    

if __name__ == '__main__':
    app.run(debug=True)
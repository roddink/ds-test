import numpy as np
import pandas as pd

from datetime import datetime, timedelta
from utils import Intervals


class TideWindow:
    """
    TideWindow enables to compute the sailable window for a given draught.
    It uses a input water depth dataframe to compute interpolate the water depth 
    of any given time with rule of 12th interpolation method.
    About rule of 12ths interpolation method, read more: 
    https://en.wikipedia.org/wiki/Rule_of_twelfths
    """
    WINDOW_LENGTH = timedelta(days=14)
    SAFETY_THRESHOLD = 0.0
    MAX_TIDE_INTERVAL = 8 * 3600
    
    def __init__(self, heights_df: pd.DataFrame):
        """
        param: heights_df: pd.DataFrame,
            The calibrated tide height dataframe
            The value of TIDE_HEIGHT_MT should be calibrated according to the base depth of the port
        """
        self.heights_df = heights_df
        self._check_tide_data_sanity()

    def _check_tide_data_sanity(self):
        self.heights_df['TIDE_DATETIME'] = self.heights_df['TIDE_DATETIME'] \
            .apply(self._strptime)
        self.heights_df = self.heights_df.dropna(subset=['TIDE_DATETIME'])
        
    @staticmethod
    def _strptime(datetime_str: str):
        try:
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            return None

    def find_tide_window(self, draught: float,
                         port: str,
                         start_time: datetime,
                         window_length=WINDOW_LENGTH,
                         safety_threshold=SAFETY_THRESHOLD) -> pd.DataFrame:
        """
        Find the tide window of given draught and port name and arrival time window.
        The returned object is a dataframe with two columns, START_DATETIME and END_DATETIME. 
        They represent the start time and end time of tide window. 
        The tide data will be validated, in order to dealing with missing tide data.
        
        The validation rule is time delta 
        between the tide records and next tide records needs to be smaller than 8 hours.
        
        param: draught, float, the ship's draught
        param: port, str, the name of arrival port
        param: start_time, datetime, the start time of the arrival time window
        param: window_length, timedelta, optional, default 14 days, the length of the arrival window
        param: safety_threshold, float, optional, default 0 meters, 
               the safety gap between draught and water depth
        
        return: pd.DataFrame, the data frame with two columns 'START_DATETIME' and 'END_DATETIME'
        """

        # port validation
        df = self.heights_df.loc[self.heights_df['PORT_NAME'] == port]
        try:
            assert not self._is_empty_dataframe(df)
        except AssertionError:
            raise ValueError(f'Unknown Port Name {port}, not exist in tide heights data')                


        # start_time and duration validation
        max_tide_interval = timedelta(seconds=self.MAX_TIDE_INTERVAL)
        df = df.loc[(df['TIDE_DATETIME'] >= start_time - max_tide_interval) &
                    (df['TIDE_DATETIME'] <= start_time + window_length + max_tide_interval)]
        try:
            assert not self._is_empty_dataframe(df)
        except AssertionError:
            raise ValueError(f'Lack of Tide Heights data for Port {port}, between {start_time} and {start_time + window_length}')
         
        # create high wave and low wave validation columns
        df = df.sort_values('TIDE_DATETIME').reset_index(drop=True)
        df['IS_VALID_TYPE'] = df['TIDE_TYPE'].apply(lambda x: 1 if x == 'HIGH' else 0)
        df['IS_VALID_TYPE'] = df['IS_VALID_TYPE'].rolling(2).sum().apply(lambda x: x==1)
        df['TIDE_SINCE_LAST'] = df['TIDE_DATETIME'].shift(-1) - df['TIDE_DATETIME'] 
        df['IS_VALID_INTERVAL'] = df['TIDE_SINCE_LAST'].apply(lambda x: x.total_seconds() < self.MAX_TIDE_INTERVAL)
        
        high_tide_interval_list = []
        for idx in range(df.shape[0] - 1):
            if df.loc[idx, 'IS_VALID_INTERVAL'] and df.loc[idx, 'IS_VALID_TYPE']:
                
                if df.loc[idx, 'TIDE_TYPE'] == 'HIGH':
                    hw = df.loc[idx, 'TIDE_HEIGHT_MT']
                    lw = df.loc[idx + 1, 'TIDE_HEIGHT_MT']
                    hw_time = df.loc[idx, 'TIDE_DATETIME']
                    lw_time = df.loc[idx + 1, 'TIDE_DATETIME']
                    
                else:  
                    hw = df.loc[idx + 1, 'TIDE_HEIGHT_MT']
                    lw = df.loc[idx, 'TIDE_HEIGHT_MT']
                    hw_time = df.loc[idx + 1, 'TIDE_DATETIME']
                    lw_time = df.loc[idx, 'TIDE_DATETIME']
                
                offset = self.interpolate_12th(draught + safety_threshold, 
                                            hw, lw, hw_time, lw_time)
                offset = timedelta(hours=offset)
                
                high_tide_interval_list.append(sorted([(hw_time - offset), hw_time]))
        
        # Merge the consecutive period
        merged_interval = Intervals(high_tide_interval_list)
        return pd.DataFrame(map(tuple, merged_interval.interval_list), columns=['START_DATETIME', 'END_DATETIME'])
       
    @staticmethod
    def _is_empty_dataframe(df: pd.DataFrame) -> bool:
        return df.shape[0] == 0
   
    @staticmethod
    def interpolate_12th(depth:float, hw:float, lw:float, 
                         hw_time:datetime, lw_time:datetime) -> float:
        """
        Compute the duration of tide height is larger than the given depth.
        The returned value is the duration between high wave time and 
        the tide reaches the given depth in hours. 
        The returned value can be negative, if the lw_time is later than hw_time 
        
        Interpolate the tide height using rule of 12ths. 
        read more at: https://en.wikipedia.org/wiki/Rule_of_twelfths

        param: depth, float, the queried water depth
        param: hw, float, the high wave height
        param: lw, float, the low wave height
        param: hw_time: datetime, the high wave time
        param: lw_time: datetime, the low wave time

        return: float, the duration between high wave time and 
        the tide reaches the given depth in hours
        """
        try:
            assert hw >= lw
        except AssertionError:
            raise ValueError('high wave should be equal or larger than low wave')
        
        time_diff = (hw_time - lw_time).total_seconds() / 3600 # convert from second to hour
        time_unit = time_diff / 6 
        norm_depth = (depth - lw) / (hw - lw) * 12
        
        def _piecewise_func(x: float):
            conditions = [x >= 12, 
                          12 > x >= 11,
                          11 > x >= 9,
                          9 > x >= 3,
                          3 > x >= 1,
                          1 > x >= 0, 
                          x < 0]
            functions = [0, 
                         lambda x: (12 - x), 
                         lambda x: (11 - x) / 2 + 1,
                         lambda x: (9 - x) / 3 + 2,
                         lambda x: (3 - x) / 2 + 4,
                         lambda x : (1 - x) + 5,
                         6]
            return np.piecewise(x, conditions, functions)
        
        return _piecewise_func(norm_depth) * time_unit


import pandas as pd
import requests

from datetime import datetime, timedelta


def get_daylight_data(lat: float, lng: float, start_date: datetime, end_date: datetime) -> dict:
    """
    Get the daylight data from api.sunrisesunset.io of given latitude, longitude, start and end date.
    For more detail: https://sunrisesunset.io/api/

    param: lat: float, latitude
    param: lng: float, longitude
    param: start_date: datetime, the start date of query window 
    param: end_date: datetime, the end date of query window

    return: dict, results returned from sunrisesunset.io
    """
    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')
    url = 'https://api.sunrisesunset.io/json?' + \
          f'lat={lat}&lng={lng}&date_start={start_date}&date_end={end_date}'
    return requests.get(url=url, timeout=60).json()


class DayLightWindow:
    """
    Find the day light of window of a port
    """
    WINDOW_LENGTH = timedelta(days=14)

    def __init__(self, port_df: pd.DataFrame):
        self.port_df = port_df
    
    def find_daylight_window(self, port_name: str, start_date: datetime, window_length=WINDOW_LENGTH) -> pd.DataFrame:
        """
        Find the daylight window from given port name, and date range
        
        """
        end_date = (start_date + window_length).date()
        start_date = start_date.date()
        
        try:
            assert port_name in self.port_df['NAME'].unique()
        except AssertionError:
            raise ValueError('port {} is not found'.format(port_name))
        
        lat = self.port_df.loc[self.port_df['NAME'] == port_name, 'LATITUDE'].values[0]
        lng = self.port_df.loc[self.port_df['NAME'] == port_name, 'LONGITUDE'].values[0]
        
        response = get_daylight_data(lat, lng, start_date, end_date)
        
        # loop over the results returned from API
        daylight_list = []
        for result in response['results']:
            daylight_list.append((datetime.strptime(result['date'] + ' ' + result['sunrise'], 
                                                    '%Y-%m-%d %I:%M:%S %p'),
                                  datetime.strptime(result['date'] + ' ' + result['sunset'], 
                                                    '%Y-%m-%d %I:%M:%S %p'))
                                )
            
        return pd.DataFrame(daylight_list, columns=['SUNRISE', 'SUNSET'])
    
   
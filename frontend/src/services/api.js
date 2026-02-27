import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export const getFireStations = () => {
  return axios.get(`${API_BASE_URL}/fire-stations/`);
};

export const reportDisaster = (data) => {
  return axios.post(`${API_BASE_URL}/disasters/`, data);
};

export const getDisaster = (id) => {
  return axios.get(`${API_BASE_URL}/disasters/${id}/`);
};

export const getActiveDisasters = () => {
  return axios.get(`${API_BASE_URL}/disasters/active/`);
};


export const pollDisasterAnalysis = (disasterId, onUpdate, maxAttempts = 20) => {
  let attempts = 0;
  
  const interval = setInterval(async () => {
    attempts++;
    
    try {
      const response = await getDisaster(disasterId);
      const disaster = response.data;
      
      // Call onUpdate with latest data every poll
      onUpdate(disaster);
      
      // Stop polling when analyzed or max attempts reached
      if (disaster.status === 'analyzed' || attempts >= maxAttempts) {
        clearInterval(interval);
      }
    } catch (error) {
      console.error('Polling error:', error);
      clearInterval(interval);
    }
  }, 3000); // every 3 seconds or max 1 min
  
  return interval;
};
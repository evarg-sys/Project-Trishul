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

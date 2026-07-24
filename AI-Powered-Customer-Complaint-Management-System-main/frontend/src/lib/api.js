import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const http = axios.create({ baseURL: API });

export async function extractFromFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await http.post("/complaints/extract", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function extractFromText(text) {
  const fd = new FormData();
  fd.append("text", text);
  const { data } = await http.post("/complaints/extract", fd);
  return data;
}

export async function saveComplaint(payload) {
  const { data } = await http.post("/complaints/save", payload);
  return data;
}

export async function chatWithAssistant(message, form) {
  const { data } = await http.post("/complaints/chat", { message, form });
  return data;
}

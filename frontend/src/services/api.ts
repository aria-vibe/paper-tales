import axios from "axios";
import type { GenerationRequest, Story } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

export async function checkHealth(): Promise<{ status: string }> {
  const { data } = await api.get("/health");
  return data;
}

export async function generateStory(
  request: GenerationRequest
): Promise<Story> {
  const formData = new FormData();
  if (request.file) {
    formData.append("file", request.file);
  }
  if (request.arxivUrl) {
    formData.append("arxiv_url", request.arxivUrl);
  }
  formData.append("age_group", request.ageGroup);
  formData.append("style", request.style);

  // TODO: Wire up to actual ADK session endpoint
  const { data } = await api.post("/generate", formData);
  return data;
}

export async function getStory(storyId: string): Promise<Story> {
  const { data } = await api.get(`/stories/${storyId}`);
  return data;
}

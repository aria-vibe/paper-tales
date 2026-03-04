import axios from "axios";
import type { GenerationRequest, Story, TopPapersResponse, VoteResponse } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 300_000,
});

export async function checkHealth(): Promise<{ status: string }> {
  const { data } = await api.get("/health");
  return data;
}

export async function generateStory(
  request: GenerationRequest,
  token: string
): Promise<Story> {
  const formData = new FormData();
  formData.append("paper_url", request.paperUrl);
  formData.append("age_group", request.ageGroup);
  formData.append("style", request.style);

  const { data } = await api.post("/api/generate", formData, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}

export async function getStory(storyId: string, token: string): Promise<Story> {
  const { data } = await api.get(`/api/stories/${storyId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}

export async function voteOnStory(
  storyId: string,
  vote: "up" | "down",
  token: string
): Promise<VoteResponse> {
  const { data } = await api.post(
    `/api/stories/${storyId}/vote`,
    { vote },
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return data;
}

export async function getTopPapers(token: string): Promise<TopPapersResponse> {
  const { data } = await api.get("/api/top-papers", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}

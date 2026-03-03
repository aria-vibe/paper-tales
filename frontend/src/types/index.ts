export type AgeGroup = "6-9" | "10-13" | "14-17";

export type StoryStyle = "fairy_tale" | "adventure" | "sci_fi" | "comic_book";

export interface StoryScene {
  text: string;
  imageUrl?: string;
  audioUrl?: string;
}

export interface Story {
  id: string;
  title: string;
  ageGroup: AgeGroup;
  style: StoryStyle;
  scenes: StoryScene[];
  glossary?: Record<string, string>;
  sourceTitle?: string;
  createdAt: string;
}

export interface GenerationRequest {
  file?: File;
  arxivUrl?: string;
  ageGroup: AgeGroup;
  style: StoryStyle;
}

export type GenerationStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "complete"
  | "error";

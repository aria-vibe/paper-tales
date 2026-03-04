import { useState } from "react";
import { voteOnStory } from "../services/api";

interface VoteButtonsProps {
  storyId: string;
  initialUpvotes: number;
  initialDownvotes: number;
  initialUserVote?: "up" | "down";
  getToken: () => Promise<string>;
}

export function VoteButtons({
  storyId,
  initialUpvotes,
  initialDownvotes,
  initialUserVote,
  getToken,
}: VoteButtonsProps) {
  const [upvotes, setUpvotes] = useState(initialUpvotes);
  const [downvotes, setDownvotes] = useState(initialDownvotes);
  const [userVote, setUserVote] = useState<"up" | "down" | undefined>(
    initialUserVote
  );
  const [loading, setLoading] = useState(false);

  async function handleVote(vote: "up" | "down") {
    if (loading) return;
    setLoading(true);
    try {
      const token = await getToken();
      const result = await voteOnStory(storyId, vote, token);
      setUpvotes(result.upvotes);
      setDownvotes(result.downvotes);
      setUserVote(result.userVote);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="vote-buttons">
      <button
        className={`vote-btn vote-up ${userVote === "up" ? "active" : ""}`}
        onClick={() => handleVote("up")}
        disabled={loading}
        aria-label="Upvote"
      >
        {"\u25B2"} {upvotes}
      </button>
      <button
        className={`vote-btn vote-down ${userVote === "down" ? "active" : ""}`}
        onClick={() => handleVote("down")}
        disabled={loading}
        aria-label="Downvote"
      >
        {"\u25BC"} {downvotes}
      </button>
    </div>
  );
}

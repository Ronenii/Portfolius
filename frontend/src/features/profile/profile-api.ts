import { apiRequest } from "../../lib/api";

export type ProfilePayload = {
  display_name: string;
  base_currency: string;
  time_horizon: string;
  investment_frequency: string;
  risk_tolerance: string | null;
  interest_tags: string[];
  excluded_sectors: string[];
  goals_note: string | null;
  goal_target_amount: string | null;
  contribution_amount: string | null;
  expected_annual_return: string | null;
};

export type Profile = ProfilePayload & {
  id: number;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export function getProfile(accessToken: string) {
  return apiRequest<Profile>("/api/v1/profile", { accessToken });
}

export function saveProfile(accessToken: string, payload: ProfilePayload) {
  return apiRequest<Profile>("/api/v1/profile", {
    accessToken,
    body: payload,
    method: "PUT",
  });
}

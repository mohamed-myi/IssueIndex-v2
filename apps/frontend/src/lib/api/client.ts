import axios, { AxiosError } from "axios";
import { getApiBaseUrl } from "./base-url";
import type { ApiErrorPayload } from "./types";

export const api = axios.create({
  baseURL: getApiBaseUrl(),
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorPayload>;
    const detail = axiosError.response?.data?.detail;
    if (detail) {
      return detail;
    }
    if (axiosError.message) {
      return axiosError.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Unknown error";
}


import { api } from "./client";
import type { NotificationRecord } from "../types/api";

export const notificationsApi = {
  list: async (unread = false) =>
    (await api.get<NotificationRecord[]>("/notifications", { params: { unread } })).data,
  markRead: async (id: string) =>
    (await api.post<NotificationRecord>(`/notifications/${id}/read`)).data,
};

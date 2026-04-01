import apiClient from "@/lib/api-client";
import type {
  DeliveryEvent,
  DeliveryMedia,
  DeliveryRoute,
  DeliveryStop,
  DriverAnnouncement,
  DriverPortalSettings,
  EventCreate,
} from "@/types/delivery";

export const driverService = {
  // -----------------------------------------------------------------------
  // Route
  // -----------------------------------------------------------------------

  async getTodayRoute(): Promise<DeliveryRoute | null> {
    const response = await apiClient.get<DeliveryRoute | null>(
      "/driver/route/today",
    );
    return response.data;
  },

  async startRoute(): Promise<DeliveryRoute> {
    const response = await apiClient.post<DeliveryRoute>(
      "/driver/route/today/start",
    );
    return response.data;
  },

  async completeRoute(totalMileage?: number): Promise<DeliveryRoute> {
    const response = await apiClient.post<DeliveryRoute>(
      "/driver/route/today/complete",
      { total_mileage: totalMileage ?? null },
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Stops
  // -----------------------------------------------------------------------

  async updateStopStatus(
    stopId: string,
    status: string,
    driverNotes?: string,
  ): Promise<DeliveryStop> {
    const response = await apiClient.patch<DeliveryStop>(
      `/driver/stops/${stopId}/status`,
      { status, driver_notes: driverNotes ?? null },
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Events
  // -----------------------------------------------------------------------

  async postEvent(data: EventCreate): Promise<DeliveryEvent> {
    const response = await apiClient.post<DeliveryEvent>(
      "/driver/events",
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Media
  // -----------------------------------------------------------------------

  // -----------------------------------------------------------------------
  // Portal Settings
  // -----------------------------------------------------------------------

  // -----------------------------------------------------------------------
  // Announcements
  // -----------------------------------------------------------------------

  async getAnnouncements(): Promise<DriverAnnouncement[]> {
    const response = await apiClient.get<DriverAnnouncement[]>(
      "/driver/announcements",
    );
    return response.data;
  },

  async acknowledgeAnnouncement(announcementId: string): Promise<void> {
    await apiClient.post(`/driver/announcements/${announcementId}/acknowledge`);
  },

  async getPortalSettings(): Promise<DriverPortalSettings> {
    const response = await apiClient.get<DriverPortalSettings>(
      "/driver/portal-settings",
    );
    return response.data;
  },

  async uploadMedia(
    deliveryId: string,
    mediaType: string,
    file: File,
  ): Promise<DeliveryMedia> {
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams({
      delivery_id: deliveryId,
      media_type: mediaType,
    });
    const response = await apiClient.post<DeliveryMedia>(
      `/driver/media?${params.toString()}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },
};

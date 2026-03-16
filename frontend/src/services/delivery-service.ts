import apiClient from "@/lib/api-client";
import type {
  Carrier,
  CarrierCreate,
  CarrierUpdate,
  Delivery,
  DeliveryCreate,
  DeliveryEvent,
  DeliveryRoute,
  DeliverySettings,
  DeliverySettingsUpdate,
  DeliveryStats,
  DeliveryStop,
  DeliveryUpdate,
  Driver,
  DriverCreate,
  DriverUpdate,
  PaginatedCarriers,
  PaginatedDeliveries,
  PaginatedDrivers,
  PaginatedRoutes,
  PaginatedVehicles,
  RouteCreate,
  RouteUpdate,
  Vehicle,
  VehicleCreate,
  VehicleUpdate,
} from "@/types/delivery";

export const deliveryService = {
  // -----------------------------------------------------------------------
  // Stats
  // -----------------------------------------------------------------------

  async getStats(): Promise<DeliveryStats> {
    const response = await apiClient.get<DeliveryStats>("/delivery/stats");
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Vehicles
  // -----------------------------------------------------------------------

  async getVehicles(
    page = 1,
    perPage = 50,
    activeOnly = true,
  ): Promise<PaginatedVehicles> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      active_only: String(activeOnly),
    });
    const response = await apiClient.get<PaginatedVehicles>(
      `/delivery/vehicles?${params.toString()}`,
    );
    return response.data;
  },

  async getVehicle(id: string): Promise<Vehicle> {
    const response = await apiClient.get<Vehicle>(`/delivery/vehicles/${id}`);
    return response.data;
  },

  async createVehicle(data: VehicleCreate): Promise<Vehicle> {
    const response = await apiClient.post<Vehicle>("/delivery/vehicles", data);
    return response.data;
  },

  async updateVehicle(id: string, data: VehicleUpdate): Promise<Vehicle> {
    const response = await apiClient.patch<Vehicle>(
      `/delivery/vehicles/${id}`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Drivers
  // -----------------------------------------------------------------------

  async getDrivers(
    page = 1,
    perPage = 50,
    activeOnly = true,
  ): Promise<PaginatedDrivers> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      active_only: String(activeOnly),
    });
    const response = await apiClient.get<PaginatedDrivers>(
      `/delivery/drivers?${params.toString()}`,
    );
    return response.data;
  },

  async getDriver(id: string): Promise<Driver> {
    const response = await apiClient.get<Driver>(`/delivery/drivers/${id}`);
    return response.data;
  },

  async createDriver(data: DriverCreate): Promise<Driver> {
    const response = await apiClient.post<Driver>("/delivery/drivers", data);
    return response.data;
  },

  async updateDriver(id: string, data: DriverUpdate): Promise<Driver> {
    const response = await apiClient.patch<Driver>(
      `/delivery/drivers/${id}`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Carriers
  // -----------------------------------------------------------------------

  async getCarriers(
    page = 1,
    perPage = 50,
    activeOnly = true,
    carrierType?: string,
  ): Promise<PaginatedCarriers> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      active_only: String(activeOnly),
    });
    if (carrierType) params.set("carrier_type", carrierType);
    const response = await apiClient.get<PaginatedCarriers>(
      `/delivery/carriers?${params.toString()}`,
    );
    return response.data;
  },

  async getCarrier(id: string): Promise<Carrier> {
    const response = await apiClient.get<Carrier>(`/delivery/carriers/${id}`);
    return response.data;
  },

  async createCarrier(data: CarrierCreate): Promise<Carrier> {
    const response = await apiClient.post<Carrier>("/delivery/carriers", data);
    return response.data;
  },

  async updateCarrier(id: string, data: CarrierUpdate): Promise<Carrier> {
    const response = await apiClient.patch<Carrier>(
      `/delivery/carriers/${id}`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Deliveries
  // -----------------------------------------------------------------------

  async getDeliveries(
    page = 1,
    perPage = 20,
    filters?: {
      status?: string;
      delivery_type?: string;
      customer_id?: string;
      carrier_id?: string;
      date_from?: string;
      date_to?: string;
      unscheduled_only?: boolean;
    },
  ): Promise<PaginatedDeliveries> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (filters?.status) params.set("status", filters.status);
    if (filters?.delivery_type)
      params.set("delivery_type", filters.delivery_type);
    if (filters?.customer_id) params.set("customer_id", filters.customer_id);
    if (filters?.carrier_id) params.set("carrier_id", filters.carrier_id);
    if (filters?.date_from) params.set("date_from", filters.date_from);
    if (filters?.date_to) params.set("date_to", filters.date_to);
    if (filters?.unscheduled_only) params.set("unscheduled_only", "true");
    const response = await apiClient.get<PaginatedDeliveries>(
      `/delivery/deliveries?${params.toString()}`,
    );
    return response.data;
  },

  async getDelivery(id: string): Promise<Delivery> {
    const response = await apiClient.get<Delivery>(
      `/delivery/deliveries/${id}`,
    );
    return response.data;
  },

  async createDelivery(data: DeliveryCreate): Promise<Delivery> {
    const response = await apiClient.post<Delivery>(
      "/delivery/deliveries",
      data,
    );
    return response.data;
  },

  async updateDelivery(id: string, data: DeliveryUpdate): Promise<Delivery> {
    const response = await apiClient.patch<Delivery>(
      `/delivery/deliveries/${id}`,
      data,
    );
    return response.data;
  },

  async updateCarrierStatus(
    deliveryId: string,
    newStatus: string,
    carrierNotes?: string,
  ): Promise<{ status: string; new_status: string }> {
    const params = new URLSearchParams({ new_status: newStatus });
    if (carrierNotes) params.set("carrier_notes", carrierNotes);
    const response = await apiClient.patch<{
      status: string;
      new_status: string;
    }>(`/delivery/deliveries/${deliveryId}/carrier-status?${params.toString()}`);
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Events
  // -----------------------------------------------------------------------

  async getDeliveryEvents(deliveryId: string): Promise<DeliveryEvent[]> {
    const response = await apiClient.get<DeliveryEvent[]>(
      `/delivery/deliveries/${deliveryId}/events`,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Routes
  // -----------------------------------------------------------------------

  async getRoutes(
    page = 1,
    perPage = 20,
    filters?: {
      route_date?: string;
      driver_id?: string;
      route_status?: string;
    },
  ): Promise<PaginatedRoutes> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (filters?.route_date) params.set("route_date", filters.route_date);
    if (filters?.driver_id) params.set("driver_id", filters.driver_id);
    if (filters?.route_status) params.set("route_status", filters.route_status);
    const response = await apiClient.get<PaginatedRoutes>(
      `/delivery/routes?${params.toString()}`,
    );
    return response.data;
  },

  async getRoute(id: string): Promise<DeliveryRoute> {
    const response = await apiClient.get<DeliveryRoute>(
      `/delivery/routes/${id}`,
    );
    return response.data;
  },

  async createRoute(data: RouteCreate): Promise<DeliveryRoute> {
    const response = await apiClient.post<DeliveryRoute>(
      "/delivery/routes",
      data,
    );
    return response.data;
  },

  async updateRoute(id: string, data: RouteUpdate): Promise<DeliveryRoute> {
    const response = await apiClient.patch<DeliveryRoute>(
      `/delivery/routes/${id}`,
      data,
    );
    return response.data;
  },

  // -----------------------------------------------------------------------
  // Route Stops
  // -----------------------------------------------------------------------

  async addStop(
    routeId: string,
    deliveryId: string,
    sequenceNumber?: number,
  ): Promise<DeliveryStop> {
    const response = await apiClient.post<DeliveryStop>(
      `/delivery/routes/${routeId}/stops`,
      { delivery_id: deliveryId, sequence_number: sequenceNumber },
    );
    return response.data;
  },

  async resequenceStops(
    routeId: string,
    stopIds: string[],
  ): Promise<{ status: string; stops: DeliveryStop[] }> {
    const response = await apiClient.patch<{
      status: string;
      stops: DeliveryStop[];
    }>(`/delivery/routes/${routeId}/stops/resequence`, { stop_ids: stopIds });
    return response.data;
  },

  async removeStop(routeId: string, stopId: string): Promise<void> {
    await apiClient.delete(`/delivery/routes/${routeId}/stops/${stopId}`);
  },

  // -----------------------------------------------------------------------
  // Settings
  // -----------------------------------------------------------------------

  async getSettings(): Promise<DeliverySettings> {
    const response =
      await apiClient.get<DeliverySettings>("/settings/delivery");
    return response.data;
  },

  async updateSettings(
    data: DeliverySettingsUpdate,
  ): Promise<DeliverySettings> {
    const response = await apiClient.put<DeliverySettings>(
      "/settings/delivery",
      data,
    );
    return response.data;
  },

  async applyPreset(presetName: string): Promise<DeliverySettings> {
    const response = await apiClient.post<DeliverySettings>(
      `/settings/delivery/preset/${presetName}`,
    );
    return response.data;
  },

  async listPresets(): Promise<{ presets: string[] }> {
    const response =
      await apiClient.get<{ presets: string[] }>("/settings/delivery/presets");
    return response.data;
  },
};

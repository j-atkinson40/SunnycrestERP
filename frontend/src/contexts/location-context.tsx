import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import apiClient from "@/lib/api-client";

interface Location {
  id: string;
  name: string;
  location_type: string;
  wilbert_territory_id?: string;
  is_primary: boolean;
  is_active: boolean;
  city?: string;
  state?: string;
}

interface LocationContextValue {
  accessibleLocations: Location[];
  selectedLocationId: string | null;
  isMultiLocation: boolean;
  setSelectedLocation: (locationId: string | null) => void;
  canAccessLocation: (locationId: string) => boolean;
  selectedLocation: Location | null;
  loading: boolean;
}

const LocationContext = createContext<LocationContextValue>({
  accessibleLocations: [],
  selectedLocationId: null,
  isMultiLocation: false,
  setSelectedLocation: () => {},
  canAccessLocation: () => false,
  selectedLocation: null,
  loading: true,
});

export function useLocations() {
  return useContext(LocationContext);
}

const STORAGE_KEY = "bridgeable_selected_location";

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  // Fetch locations on auth
  useEffect(() => {
    if (!isAuthenticated) {
      setLocations([]);
      setLoading(false);
      return;
    }
    apiClient
      .get("/locations")
      .then((r) => {
        setLocations(r.data || []);
        // If stored selection is no longer valid, reset
        if (selectedId && !r.data.some((l: Location) => l.id === selectedId)) {
          setSelectedId(null);
          localStorage.removeItem(STORAGE_KEY);
        }
      })
      .catch(() => setLocations([]))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  const isMultiLocation = locations.length > 1;

  const setSelectedLocation = useCallback((id: string | null) => {
    setSelectedId(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const canAccessLocation = useCallback(
    (id: string) => locations.some((l) => l.id === id),
    [locations]
  );

  const selectedLocation = selectedId
    ? locations.find((l) => l.id === selectedId) ?? null
    : null;

  return (
    <LocationContext.Provider
      value={{
        accessibleLocations: locations,
        selectedLocationId: selectedId,
        isMultiLocation,
        setSelectedLocation,
        canAccessLocation,
        selectedLocation,
        loading,
      }}
    >
      {children}
    </LocationContext.Provider>
  );
}

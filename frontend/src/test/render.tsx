import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import { AppRoutes } from "../app/AppRoutes";
import { createQueryClient } from "../app/queryClient";

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

/** Приложение целиком по адресу `route`: настоящие маршруты, настоящий кэш, сеть — MSW. */
export function renderApp(route = "/"): { queryClient: QueryClient } {
  const queryClient = createQueryClient();
  // Повторы запросов замедляли бы тесты ошибок; поведение повторов проверяется отдельно.
  queryClient.setDefaultOptions({
    queries: { retry: false },
    mutations: { retry: false },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { queryClient };
}

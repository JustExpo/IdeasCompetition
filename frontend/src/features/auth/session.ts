import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchCurrentUser, logIn, logOut, register, type User } from "../../api";

/** Ключ запроса текущего пользователя: `null` в кэше означает «не вошёл». */
export const sessionKey = ["session"] as const;

export function useSession() {
  return useQuery<User | null>({
    queryKey: sessionKey,
    queryFn: fetchCurrentUser,
    staleTime: 30_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logIn,
    onSuccess: (user) => {
      queryClient.setQueryData(sessionKey, user);
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: register,
    // Сервер сразу открывает сессию, второй вход не нужен.
    onSuccess: (user) => {
      queryClient.setQueryData(sessionKey, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logOut,
    onSettled: () => {
      // Данные прежнего пользователя не должны остаться в кэше для следующего.
      // `clear()` отцепил бы от кэша уже подписанные компоненты, поэтому сессию обновляем на месте.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== sessionKey[0] });
      queryClient.setQueryData(sessionKey, null);
    },
  });
}

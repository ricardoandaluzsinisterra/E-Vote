export function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("auth_token");

  if (!token) {
    throw new Error("No authentication token found");
  }

  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
  };
}

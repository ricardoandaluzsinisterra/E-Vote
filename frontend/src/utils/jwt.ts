export function decodeJWT(token: string) {
  // Split token by dots, get middle part (payload)
  const base64Url = token.split(".")[1];

  // Convert Base64URL to Base64 (replace special chars)
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");

  // Decode Base64 to JSON string
  // This complex part handles UTF-8 encoding properly
  const jsonPayload = decodeURIComponent(
    atob(base64)
      .split("")
      .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
      .join("")
  );

  // Parse JSON string to object
  return JSON.parse(jsonPayload);
}

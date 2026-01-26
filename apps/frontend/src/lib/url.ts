export function setQueryParam(url: URL, key: string, value: string | null) {
  if (value === null || value === "") {
    url.searchParams.delete(key);
    return;
  }
  url.searchParams.set(key, value);
}


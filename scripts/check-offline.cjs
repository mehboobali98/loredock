// Run inside the application container after enabling the offline override.
async function probe(url, method = "GET") {
  try {
    const response = await fetch(url, { method, signal: AbortSignal.timeout(8_000) });
    return { reachable: true, status: response.status };
  } catch (error) {
    return { reachable: false, error: error.name };
  }
}

async function main() {
  const result = {
    local_model: await probe("http://ollama-relay:11434/api/version"),
    downloads: await probe("http://ollama-relay:11434/api/pull", "POST"),
    external_https: await probe("https://example.com"),
  };
  result.passed = result.local_model.status === 200 &&
    result.downloads.status === 403 && !result.external_https.reachable;
  console.log(JSON.stringify(result));
  process.exitCode = result.passed ? 0 : 1;
}

main().catch(() => { process.exitCode = 1; });

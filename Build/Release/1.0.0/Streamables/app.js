export default {
  version: "{version}",
  screens: {
    main: "/Build/Release/{version}/assets/ui/index.json"
  },
  actions: {
    setStatus(text) {
      return [
        { "op": "set", "id": "status", "prop": "text", "value": String(text) }
      ];
    },
    onSolveSuccess(signature) {
      return [
        { "op": "set", "id": "status", "prop": "text", "value": "signature: " + String(signature) },
        { "op": "set", "id": "solveBtn", "prop": "enabled", "value": false }
      ];
    },
    onSolveError() {
      return [
        { "op": "set", "id": "status", "prop": "text", "value": "error" }
      ];
    }
  }
}

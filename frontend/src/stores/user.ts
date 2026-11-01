import { defineStore } from "pinia"
import { ref } from "vue"

export const useUserStore = defineStore("user", () => {
  const token = ref<string>(localStorage.getItem("token") || "")

  function setToken(newToken: string): void {
    token.value = newToken
    localStorage.setItem("token", newToken)
  }

  function logout(): void {
    token.value = ""
    localStorage.removeItem("token")
  }

  return { token, setToken, logout }
})

/**
 * Config store — platform-level configuration hydrated from the API.
 * The kill switch state drives the KillSwitchBanner visibility.
 */
import { create } from 'zustand'

interface ConfigState {
  killSwitchEnabled: boolean
  setKillSwitch: (enabled: boolean) => void
}

export const useConfigStore = create<ConfigState>((set) => ({
  killSwitchEnabled: false,
  setKillSwitch: (enabled) => set({ killSwitchEnabled: enabled }),
}))

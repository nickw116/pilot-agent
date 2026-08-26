import { ref, onMounted, onBeforeUnmount } from 'vue'
import { API_BASE } from '../constants/index.js'

/**
 * 轻量健康检查 composable：
 * - 每 15 秒探测 /api/health，fetch 超时 10 秒（适应移动端弱网环境）
 * - 单次失败不立即计数，而是等待 1 秒后补发一次快速探测（3 秒超时）：
 *   补测成功 → 视为瞬时抖动（典型场景：手机回到前台时网络尚在重连），不计失败；
 *   补测也失败 → 计 1 次失败，连续 2 次失败才判定 serviceStatus = 'down'
 * - 区分失败原因并通过 downReason 暴露：
 *   'network' = 请求根本发不出去（断网/弱网）；'timeout' = 服务可达但无响应（阻塞/网关错误）
 *   调用方据此展示准确文案，避免误导用户以为服务在重启
 * - 任意一次探测成功立即重置失败计数，快速恢复信任
 * - 恢复 → serviceStatus = 'recovered'（绿色提示，3 秒后自动消失）
 */
export function useServiceStatus() {
  const serviceStatus = ref('up') // 'up' | 'down' | 'recovered'
  const downReason = ref('network') // 'network' | 'timeout'
  let timer = null
  let recoverTimer = null
  let wasDown = false
  let failCount = 0
  let probing = false

  // 返回 'ok' | 'timeout' | 'network'
  async function probe(timeoutMs) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const resp = await fetch(`${API_BASE}/health`, { cache: 'no-store', signal: controller.signal })
      return resp.ok ? 'ok' : 'timeout'
    } catch (err) {
      // AbortError 是我们自己的超时；其余（TypeError 等）是网络不可达
      return err?.name === 'AbortError' ? 'timeout' : 'network'
    } finally {
      clearTimeout(timeout)
    }
  }

  async function check() {
    if (probing) return
    probing = true
    try {
      const first = await probe(10000)
      if (first === 'ok') {
        markUp()
        return
      }
      // 稍等片刻让网络稳定（回前台重连场景），再立即补测一次，
      // 只有连续两次（跨周期）都失败才真正计一次失败
      await new Promise(resolve => setTimeout(resolve, 1000))
      const recheck = await probe(3000)
      if (recheck === 'ok') {
        markUp()
        return
      }
      downReason.value = first === 'network' && recheck === 'network' ? 'network' : 'timeout'
      markDown()
    } finally {
      probing = false
    }
  }

  function markUp() {
    failCount = 0
    if (wasDown) {
      serviceStatus.value = 'recovered'
      wasDown = false
      if (recoverTimer) clearTimeout(recoverTimer)
      recoverTimer = setTimeout(() => {
        if (serviceStatus.value === 'recovered') {
          serviceStatus.value = 'up'
        }
      }, 3000)
    }
  }

  function markDown() {
    failCount++
    if (failCount >= 2 && !wasDown) {
      wasDown = true
      serviceStatus.value = 'down'
    }
  }

  onMounted(() => {
    check()
    timer = setInterval(check, 15000)
  })

  onBeforeUnmount(() => {
    if (timer) clearInterval(timer)
    if (recoverTimer) clearTimeout(recoverTimer)
  })

  return { serviceStatus, downReason }
}

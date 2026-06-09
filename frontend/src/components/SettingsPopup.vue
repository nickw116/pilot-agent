<template>
  <van-popup v-model:show="visible" position="bottom" round class="settings-popup">
    <div class="settings-panel">
      <h3>{{ showChangePassword ? '修改密码' : '设置' }}</h3>

      <template v-if="!showChangePassword">
        <van-cell-group inset class="settings-fields">
          <van-cell title="用户" :value="userDisplay" />
          <van-cell title="Session">
            <template #value>
              <code class="session-code">{{ sessionKey }}</code>
            </template>
          </van-cell>
        </van-cell-group>

        <van-button block class="settings-btn settings-btn-outline" @click="showChangePassword = true">
          修改密码
        </van-button>
        <van-button block class="settings-btn settings-btn-primary" @click="handleClearChat">
          清空对话
        </van-button>
        <van-button block type="default" class="settings-btn settings-btn-default" @click="handleLogout">
          退出登录
        </van-button>
      </template>

      <template v-else>
        <div class="change-password-form">
          <van-field
            v-model="oldPassword"
            type="password"
            label="旧密码"
            placeholder="输入当前密码"
            clearable
            class="pw-field"
          />
          <van-field
            v-model="newPassword"
            type="password"
            label="新密码"
            placeholder="至少 6 位"
            clearable
            class="pw-field"
          />
          <van-field
            v-model="confirmPassword"
            type="password"
            label="确认密码"
            placeholder="再次输入新密码"
            clearable
            class="pw-field"
          />
          <p v-if="pwError" class="pw-error">{{ pwError }}</p>
          <van-button
            block
            class="settings-btn settings-btn-primary"
            :loading="pwLoading"
            @click="handleChangePassword"
          >
            确认修改
          </van-button>
          <van-button block type="default" class="settings-btn settings-btn-default" @click="resetPwForm">
            返回
          </van-button>
        </div>
      </template>
    </div>
  </van-popup>
</template>

<script setup>
import { ref, computed } from 'vue'
import { showDialog } from 'vant'

const props = defineProps({
  show: { type: Boolean, default: false },
  currentUser: { type: Object, default: null },
  sessionKey: { type: String, default: '' },
})

const emit = defineEmits(['update:show', 'clear-chat', 'logout', 'change-password'])

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const userDisplay = computed(() => {
  if (!props.currentUser) return ''
  return props.currentUser.displayName || props.currentUser.username || ''
})

const showChangePassword = ref(false)
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const pwError = ref('')
const pwLoading = ref(false)

function resetPwForm() {
  showChangePassword.value = false
  oldPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  pwError.value = ''
}

async function handleChangePassword() {
  pwError.value = ''
  if (!oldPassword.value) { pwError.value = '请输入旧密码'; return }
  if (!newPassword.value) { pwError.value = '请输入新密码'; return }
  if (newPassword.value.length < 6) { pwError.value = '新密码至少 6 位'; return }
  if (newPassword.value !== confirmPassword.value) { pwError.value = '两次输入的新密码不一致'; return }
  if (newPassword.value === oldPassword.value) { pwError.value = '新密码不能与旧密码相同'; return }

  pwLoading.value = true
  emit('change-password', oldPassword.value, newPassword.value, (result) => {
    pwLoading.value = false
    if (result.ok) {
      showDialog({ title: '成功', message: '密码已修改，请重新登录' })
      emit('update:show', false)
    } else {
      pwError.value = result.message
    }
  })
}

function handleClearChat() {
  emit('clear-chat')
}

function handleLogout() {
  emit('logout')
}
</script>

<style>
.settings-popup.van-popup {
  background: var(--color-bg-secondary);
}
.settings-panel {
  padding: 24px 16px 36px;
}
.settings-panel h3 {
  font-family: 'Space Grotesk', sans-serif;
  text-align: center;
  margin-bottom: 20px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
}
.session-code {
  font-size: 12px;
}
.settings-fields { border-radius: 16px; overflow: hidden; }
.settings-btn {
  margin-top: 16px;
  height: 46px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 600;
  font-family: 'DM Sans', sans-serif;
}
.settings-btn-primary.van-button {
  margin-top: 20px;
  background: var(--color-accent);
  border: none;
  color: white;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}
.settings-btn-default.van-button {
  margin-top: 16px;
  background: rgba(99, 102, 241, 0.06);
  border: 1.5px solid var(--color-border);
  color: var(--color-primary);
}
.settings-btn-outline.van-button {
  margin-top: 16px;
  background: var(--color-bg-glass);
  border: 1.5px solid var(--color-primary);
  color: var(--color-primary);
}
.settings-btn:active { transform: scale(0.98); }
.change-password-form {
  display: flex;
  flex-direction: column;
}
.pw-field.van-cell {
  border-radius: 12px;
  margin-bottom: 12px;
  background: var(--color-bg-glass);
  border: 1.5px solid var(--color-border);
}
.pw-field:focus-within {
  border-color: var(--color-primary);
}
.pw-error {
  color: var(--color-danger);
  font-size: 13px;
  text-align: center;
  margin-bottom: 12px;
}
</style>

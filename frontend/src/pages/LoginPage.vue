<template>
  <div class="login-page">
    <div class="login-box">
      <!-- CSS Robot Icon -->
      <div class="bot-icon">
        <div class="bot-head"></div>
        <div class="bot-eye left"></div>
        <div class="bot-eye right"></div>
        <div class="bot-mouth"></div>
        <div class="bot-antenna"></div>
      </div>
      <h2>PILOT AGENT</h2>
      <van-cell-group inset class="login-fields">
        <van-field :model-value="username" @update:model-value="$emit('update:username', $event)" label="用户名" placeholder="用户名" />
        <van-field :model-value="password" @update:model-value="$emit('update:password', $event)" label="密码" type="password" placeholder="密码" />
      </van-cell-group>
      <van-button type="primary" block class="login-btn" @click="$emit('login')">
        进入
      </van-button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  username: { type: String, default: '' },
  password: { type: String, default: '' },
})

defineEmits(['update:username', 'update:password', 'login'])
</script>

<style>
/* ── Login Page ── */
.login-page {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  background: var(--color-bg);
  padding: 20px;
  overflow: hidden;
}
.login-page::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 50%, rgba(139, 92, 246, 0.04) 0%, transparent 50%);
  animation: bg-drift 20s ease-in-out infinite alternate;
}
@keyframes bg-drift {
  from { transform: translate(0, 0) rotate(0deg); }
  to { transform: translate(-2%, -1%) rotate(2deg); }
}
.login-box {
  position: relative;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--color-border);
  border-radius: 24px;
  padding: 40px 28px;
  width: 100%;
  max-width: 380px;
  box-shadow: var(--shadow-lg);
  animation: fadeInUp 0.6s ease;
}
.login-box::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), transparent 40%, transparent 60%, rgba(139, 92, 246, 0.15));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}
.login-box h2 {
  font-family: 'Space Grotesk', sans-serif;
  text-align: center;
  margin-bottom: 28px;
  color: var(--color-text);
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 2px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* CSS Robot Icon */
.bot-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  position: relative;
}
.bot-head {
  width: 48px;
  height: 40px;
  background: var(--color-bg-secondary);
  border-radius: 12px;
  border: 1px solid var(--color-border);
  position: absolute;
  left: 8px;
  top: 14px;
}
.bot-eye {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: 50%;
  position: absolute;
  top: 28px;
  box-shadow: 0 0 6px rgba(99, 102, 241, 0.4);
}
.bot-eye.left { left: 18px; }
.bot-eye.right { right: 18px; }
.bot-mouth {
  width: 20px;
  height: 6px;
  border-bottom: 3px solid var(--color-primary);
  border-radius: 0 0 10px 10px;
  position: absolute;
  bottom: 18px;
  left: 50%;
  transform: translateX(-50%);
}
.bot-antenna {
  width: 4px;
  height: 12px;
  background: var(--color-primary-light);
  position: absolute;
  top: 2px;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 2px;
}
.bot-antenna::after {
  content: '';
  width: 10px;
  height: 10px;
  background: var(--color-primary);
  border-radius: 50%;
  position: absolute;
  top: -6px;
  left: -3px;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.2);
  animation: antenna-glow 2s ease-in-out infinite;
}
@keyframes antenna-glow {
  0%, 100% { box-shadow: 0 0 10px rgba(99, 102, 241, 0.2); }
  50% { box-shadow: 0 0 18px rgba(99, 102, 241, 0.35); }
}

.login-fields { margin-top: 0; }
.login-fields .van-cell-group--inset { margin: 0; }
.login-btn {
  margin-top: 28px;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  font-family: 'Space Grotesk', sans-serif;
}
.login-btn.van-button {
  margin-top: 28px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border: none;
  color: #fff;
  box-shadow: var(--shadow-md), 0 4px 16px rgba(99, 102, 241, 0.15);
  transition: all 0.3s ease;
}
.login-btn.van-button:hover {
  box-shadow: var(--shadow-lg), 0 6px 24px rgba(99, 102, 241, 0.2);
  transform: translateY(-2px);
}
.login-btn:active { transform: scale(0.97) translateY(0); }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>

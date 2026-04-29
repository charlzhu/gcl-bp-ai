<template>
  <section class="trial-page">
    <div class="intro">
      <h1>试运行说明</h1>
      <p>能答则答，缺条件则追问，不能答则说明原因。</p>
    </div>

    <div class="grid">
      <article>
        <h2>可问</h2>
        <p>物流统计、BOM 材料规格和订单对比。</p>
      </article>
      <article>
        <h2>会追问</h2>
        <p>缺订单、材料、版本、范围或口径时。</p>
      </article>
      <article>
        <h2>会说明</h2>
        <p>当前数据或业务规则不支撑时。</p>
      </article>
    </div>

    <div class="boundary">
      <h2>边界</h2>
      <ul>
        <li>不查数，不生成 SQL，不修改业务边界。</li>
        <li>只做理解辅助和表达优化。</li>
        <li>不编造订单、物料、版本、规格或物流统计结果。</li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.trial-page {
  width: min(880px, calc(100vw - 360px));
  margin: 48px auto 0;
  display: grid;
  gap: 16px;
  font-size: 14px;
}

.intro,
.grid article,
.boundary {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 18px 20px;
}

h1,
h2 {
  margin: 0;
  color: #111827;
}

h1 {
  font-size: 24px;
  font-weight: 600;
}

h2 {
  font-size: 16px;
  font-weight: 600;
}

p,
li {
  color: #617484;
  line-height: 1.7;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

ul {
  margin: 10px 0 0;
  padding-left: 18px;
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .trial-page {
    width: calc(100vw - 32px);
    margin-top: 24px;
  }
}
</style>

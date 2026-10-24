import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 🚨 就是这一行丢了！访问根路径 / 时，自动重定向到 /login
    {
      path: "/",
      redirect: "/login",
    },
    {
      path: "/login",
      name: "Login",
      component: () => import("../views/Login.vue"),
    },
    {
      path: "/home",
      name: "Home",
      component: () => import("../views/Home.vue"),
    },
    {
      path: "/interview",
      name: "Interview",
      component: () => import("../views/Interview.vue"),
    },
    {
      path: "/report",
      name: "Report",
      component: () => import("../views/Report.vue"),
    },
  ],
});

// 路由守卫：没登录不让进主页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("token");
  if (to.name !== "Login" && !token) {
    next({ name: "Login" });
  } else {
    next();
  }
});

export default router;

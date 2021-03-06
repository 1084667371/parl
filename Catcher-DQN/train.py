#   Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#-*- coding: utf-8 -*-

import os
import gym
import numpy as np
import parl
from parl.utils import logger  # 日志打印工具
from ple import PLE
from ple.games.catcher import Catcher
from model import Model
from algorithm import DQN  # from parl.algorithms import DQN  # parl >= 1.3.1
from agent import Agent

from replay_memory import ReplayMemory

LEARN_FREQ = 5  # 训练频率，不需要每一个step都learn，攒一些新增经验后再learn，提高效率
MEMORY_SIZE = 20000  # replay memory的大小，越大越占用内存
MEMORY_WARMUP_SIZE = 200  # replay_memory 里需要预存一些经验数据，再从里面sample一个batch的经验让agent去learn
BATCH_SIZE = 32  # 每次给agent learn的数据数量，从replay memory随机里sample一批数据出来
LEARNING_RATE = 0.0001  # 学习率
GAMMA = 0.99  # reward 的衰减因子，一般取 0.9 到 0.999 不等


# 训练一个episode
def run_episode(env, agent, rpm):
    total_reward = 0
    env.reset_game()
    obs = list(env.getGameState().values())
    step = 0
    while True:
        step += 1
        action_index = agent.sample(obs)  # 采样动作，所有动作都有概率被尝试到
        action = env.getActionSet()[action_index]
        # 行动
        reward = env.act(action)
        next_obs = list(env.getGameState().values())
        done = env.game_over()
        rpm.append((obs, action_index, reward, next_obs, done))

        # train model
        if (len(rpm) > MEMORY_WARMUP_SIZE) and (step % LEARN_FREQ == 0):
            (batch_obs, batch_action, batch_reward, batch_next_obs,
             batch_done) = rpm.sample(BATCH_SIZE)
            train_loss = agent.learn(batch_obs, batch_action, batch_reward,
                                     batch_next_obs,
                                     batch_done)  # s,a,r,s',done

        total_reward += reward
        obs = next_obs
        if done:
            break
    return total_reward


# 评估 agent, 跑 5 个episode，总reward求平均
def evaluate(env, agent, render=False):
    eval_reward = []
    for i in range(5):
        env.reset_game()
        obs = list(env.getGameState().values())
        episode_reward = 0
        while True:
            action = agent.predict(obs)  # 预测动作，只选最优动作
            action = env.getActionSet()[action]
            reward = env.act(action)
            obs = list(env.getGameState().values())
            episode_reward += reward
            if render:
                env.getScreenRGB()
            if env.game_over():
                break
        eval_reward.append(episode_reward)
    return np.mean(eval_reward)


def main():
    # 创建环境
    env = Catcher()
    env = PLE(env, fps=30, display_screen=True, force_fps=True)
    # 根据parl框架构建agent
    act_dim = len(env.getActionSet())
    obs_dim = len(env.getGameState())
    rpm = ReplayMemory(MEMORY_SIZE)  # DQN的经验回放池

    model = Model(act_dim=act_dim)
    alg = DQN(model, act_dim=act_dim, gamma=GAMMA, lr=LEARNING_RATE)
    agent = Agent(alg, obs_dim=obs_dim, act_dim=act_dim,e_greed_decrement=0.1,e_greed=1e-6)  # e_greed有一定概率随机选取动作，探索

    # 加载模型
    if os.path.exists('./Catcher.ckpt'):
       agent.restore('./Catcher.ckpt')
    # 先往经验池里存一些数据，避免最开始训练的时候样本丰富度不够
    while len(rpm) < MEMORY_WARMUP_SIZE:
        run_episode(env, agent, rpm)

    max_episode = 2000

    # start train
    episode = 0
    while episode < max_episode:  # 训练max_episode个回合，test部分不计算入episode数量
        # train part
        for i in range(0, 50):
            total_reward = run_episode(env, agent, rpm)
            episode += 1

        # test part
        eval_reward = evaluate(env, agent, render=True)  # render=True 查看显示效果
        logger.info('episode:{}    e_greed:{}   Test reward:{}'.format(
            episode, agent.e_greed, eval_reward))

    # 训练结束，保存模型
    save_path = './Catcher.ckpt'
    agent.save(save_path)


if __name__ == '__main__':
    main()
